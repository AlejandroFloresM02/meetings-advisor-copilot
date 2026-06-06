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


class HttpxFetcher:
    """Live fetcher. `verify` is overridable for the corporate TLS proxy."""

    def __init__(self, verify: bool = True, timeout: float = 20.0):
        self.verify = verify
        self.timeout = timeout

    def fetch(self, url: str) -> FetchedDoc:
        import datetime

        import httpx

        resp = httpx.get(
            url, verify=self.verify, timeout=self.timeout, follow_redirects=True
        )
        resp.raise_for_status()
        return FetchedDoc.from_bytes(
            url=url,
            fetched_at=datetime.date.today(),
            content_type=resp.headers.get("content-type", "application/octet-stream"),
            body=resp.content,
        )
