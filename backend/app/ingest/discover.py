"""SearXNG discoverer port (spec §4) + record/replay.

Calls a self-hosted SearXNG JSON API via the Fetcher port (so it inherits
record/replay), then filters to the allowlisted domains. Discover is an
optimization: descriptors with a canonical URL skip it (see pipeline).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from urllib.parse import quote_plus, urlparse

from pydantic import BaseModel, TypeAdapter

from app.ingest.fetch import Fetcher, cassette_name


class SearchResult(BaseModel):
    url: str
    title: str = ""


class Discoverer(Protocol):
    def discover(
        self, query: str, allowed_domains: list[str]
    ) -> list[SearchResult]: ...


def _on_allowlist(url: str, allowed_domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


class SearxngDiscoverer:
    def __init__(self, base_url: str, fetcher: Fetcher):
        self.base_url = base_url.rstrip("/")
        self.fetcher = fetcher

    def discover(self, query: str, allowed_domains: list[str]) -> list[SearchResult]:
        url = f"{self.base_url}/search?format=json&q={quote_plus(query)}"
        doc = self.fetcher.fetch(url)
        payload = json.loads(doc.text())
        out = []
        for r in payload.get("results", []):
            u = r.get("url", "")
            if u and _on_allowlist(u, allowed_domains):
                out.append(SearchResult(url=u, title=r.get("title", "")))
        return out


_RESULTS = TypeAdapter(list[SearchResult])


class ReplayDiscoverer:
    def __init__(self, cassette_dir: Path):
        self.dir = Path(cassette_dir)

    def discover(self, query: str, allowed_domains: list[str]) -> list[SearchResult]:
        path = self.dir / cassette_name("discover", query)
        if not path.exists():
            raise FileNotFoundError(f"no discover cassette for {query!r} at {path}")
        return _RESULTS.validate_json(path.read_text(encoding="utf-8"))


class RecordingDiscoverer:
    def __init__(self, inner: Discoverer, cassette_dir: Path):
        self.inner = inner
        self.dir = Path(cassette_dir)

    def discover(self, query: str, allowed_domains: list[str]) -> list[SearchResult]:
        results = self.inner.discover(query, allowed_domains)
        path = self.dir / cassette_name("discover", query)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _RESULTS.dump_json(results, indent=2).decode("utf-8"), encoding="utf-8"
        )
        return results
