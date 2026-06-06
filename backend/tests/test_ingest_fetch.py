from datetime import date

import pytest

from app.ingest.fetch import RecordingFetcher, ReplayFetcher, cassette_name
from app.ingest.models import FetchedDoc


class _StubFetcher:
    """In-memory Fetcher double for exercising record/replay."""

    def __init__(self, docs: dict[str, FetchedDoc]):
        self.docs = docs

    def fetch(self, url: str) -> FetchedDoc:
        return self.docs[url]


def test_cassette_name_is_stable_and_safe():
    n = cassette_name("fetch", "https://x.gov/A b?c=1")
    assert n.startswith("fetch/")
    assert n.endswith(".json")
    assert " " not in n


def test_record_then_replay_roundtrip(tmp_path):
    url = "https://publicplansdata.org/x"
    doc = FetchedDoc.from_text(url, date(2026, 6, 1), "text/html", "<p>hi</p>")
    rec = RecordingFetcher(_StubFetcher({url: doc}), tmp_path)
    out = rec.fetch(url)  # records a cassette
    assert out.text() == "<p>hi</p>"

    replay = ReplayFetcher(tmp_path)
    again = replay.fetch(url)
    assert again.url == url
    assert again.text() == "<p>hi</p>"


def test_replay_missing_cassette_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReplayFetcher(tmp_path).fetch("https://nope.gov")
