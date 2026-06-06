from datetime import date

from app.ingest.discover import RecordingDiscoverer, ReplayDiscoverer, SearxngDiscoverer
from app.ingest.models import FetchedDoc


class _StubFetcher:
    def __init__(self, payload: str):
        self.payload = payload

    def fetch(self, url: str) -> FetchedDoc:
        return FetchedDoc.from_text(
            url, date(2026, 6, 1), "application/json", self.payload
        )


def test_searxng_parses_results_and_filters_allowlist():
    payload = (
        '{"results": ['
        '{"url": "https://www.calpers.ca.gov/page/about/board", "title": "Board"},'
        '{"url": "https://evil.example.com/x", "title": "Off allowlist"}]}'
    )
    disc = SearxngDiscoverer("http://localhost:8080", _StubFetcher(payload))
    results = disc.discover("CalPERS board", ["calpers.ca.gov"])
    assert len(results) == 1
    assert results[0].url.endswith("/about/board")


def test_discover_record_then_replay(tmp_path):
    payload = '{"results": [{"url": "https://www.calpers.ca.gov/x", "title": "X"}]}'
    inner = SearxngDiscoverer("http://localhost:8080", _StubFetcher(payload))
    rec = RecordingDiscoverer(inner, tmp_path)
    out = rec.discover("q", ["calpers.ca.gov"])
    assert out[0].title == "X"

    replay = ReplayDiscoverer(tmp_path)
    assert (
        replay.discover("q", ["calpers.ca.gov"])[0].url
        == "https://www.calpers.ca.gov/x"
    )
