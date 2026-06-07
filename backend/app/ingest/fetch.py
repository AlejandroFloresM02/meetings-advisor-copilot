"""Fetcher port (spec §4) + record/replay adapters.

The cassette is a committed/seedable JSON file per (kind, key); ReplayFetcher
serves it offline, RecordingFetcher writes it from a live call. Tests seed
cassettes into tmp_path; the real CalPERS recording is the `--refresh-fixtures`
live path.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

from app.ingest.models import FetchedDoc


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchedDoc: ...


def cassette_name(kind: str, key: str) -> str:
    """Human-readable, collision-free cassette path: '<kind>/<slug>-<hash>.json'."""
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:60]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return f"{kind}/{slug}-{digest}.json"


class ReplayFetcher:
    def __init__(self, cassette_dir: Path):
        self.dir = Path(cassette_dir)

    def fetch(self, url: str) -> FetchedDoc:
        path = self.dir / cassette_name("fetch", url)
        if not path.exists():
            raise FileNotFoundError(f"no fetch cassette for {url} at {path}")
        return FetchedDoc.model_validate_json(path.read_text(encoding="utf-8"))


class RecordingFetcher:
    def __init__(self, inner: Fetcher, cassette_dir: Path):
        self.inner = inner
        self.dir = Path(cassette_dir)

    def fetch(self, url: str) -> FetchedDoc:
        doc = self.inner.fetch(url)
        path = self.dir / cassette_name("fetch", url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        return doc


# A browser-like User-Agent: many public sites/APIs (PPD, trade press) return
# 403 to the default python-httpx UA. Overridable per instance.
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class HttpxFetcher:
    """Live fetcher. `verify` is overridable for the corporate TLS proxy."""

    def __init__(
        self,
        verify: bool = True,
        timeout: float = 20.0,
        user_agent: str = _DEFAULT_UA,
    ):
        self.verify = verify
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, url: str) -> FetchedDoc:
        import datetime

        import httpx

        try:
            resp = httpx.get(
                url,
                verify=self.verify,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Some public edges (e.g. PPD's Fastly WAF) fingerprint-block httpx's
            # TLS while allowing the system curl. Fall back on 403.
            if exc.response.status_code == 403:
                return _curl_fetch(url, self.user_agent, self.verify, self.timeout)
            raise
        return FetchedDoc.from_bytes(
            url=url,
            fetched_at=datetime.date.today(),
            content_type=resp.headers.get("content-type", "application/octet-stream"),
            body=resp.content,
        )


def _curl_fetch(url: str, user_agent: str, verify: bool, timeout: float) -> FetchedDoc:
    """Fallback fetch via the system curl, whose TLS fingerprint passes WAFs that
    block httpx. Headers stream to stdout (-D -), the body to a temp file (so
    binary like PDFs is preserved); content-type is the last response header."""
    import datetime
    import os
    import re
    import shutil
    import subprocess
    import tempfile

    fd, body_path = tempfile.mkstemp()
    os.close(fd)
    try:
        curl = shutil.which("curl")
        if curl is None:
            raise RuntimeError("curl not found (needed for the WAF fallback fetch)")
        cmd = [curl, "-sSL", "-A", user_agent, "--max-time", str(int(timeout) + 5)]
        if not verify:
            cmd.append("-k")
        cmd += ["-D", "-", "-o", body_path, url]
        proc = subprocess.run(  # noqa: S603 - curl with an allowlisted source URL
            cmd, capture_output=True, timeout=int(timeout) + 15
        )
        if proc.returncode != 0:
            msg = proc.stderr.decode("utf-8", "replace")[:200]
            raise RuntimeError(f"curl fallback failed ({proc.returncode}): {msg}")
        headers = proc.stdout.decode("latin-1", "replace")
        types = re.findall(r"(?im)^content-type:\s*(.+?)\s*$", headers)
        content_type = types[-1] if types else "application/octet-stream"
        with open(body_path, "rb") as fh:
            body = fh.read()
    finally:
        os.unlink(body_path)
    return FetchedDoc.from_bytes(
        url=url,
        fetched_at=datetime.date.today(),
        content_type=content_type,
        body=body,
    )
