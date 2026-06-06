from datetime import date
from pathlib import Path

from app.ingest.discover import RecordingDiscoverer, ReplayDiscoverer, SearchResult
from app.ingest.extract.llm_port import RecordingLlmExtractor, ReplayLlmExtractor
from app.ingest.fetch import RecordingFetcher, ReplayFetcher
from app.ingest.models import FetchedDoc
from app.ingest.pipeline import ingest_client

DATA = Path(__file__).resolve().parents[1] / "data"

_PPD = '{"FundedRatio": 0.75, "ActuarialAssumedInterest": 0.068, "TotalPlanAssets_mm": 502000.0, "FiscalYear": 2025, "Allocation": [{"asset_class": "Fixed Income", "target_pct": 30.0, "actual_pct": 28.0}]}'
_BOARD = "<html><body><h3>Chief Investment Officer</h3></body></html>"
_NEWS = "<html><body>CalPERS placed a manager on watch.</body></html>"
_ACFR = "CalPERS ACFR FY2025 funded ratio 75 percent."


class _StubFetcher:
    def __init__(self, docs):
        self.docs = docs

    def fetch(self, url):
        return self.docs[url]


class _RouterLlm:
    """Routes by a marker in the system prompt to the right canned payload."""

    def extract(self, system, user):
        s = system.lower()
        if "seat" in s:
            return {
                "seats": [
                    {
                        "id": "SEAT-CIO",
                        "title": "Chief Investment Officer",
                        "decides": "Allocation",
                        "priorities": ["cost-efficiency"],
                    }
                ]
            }
        if "action" in s:
            return {
                "actions": [
                    {
                        "id": "ACT-1",
                        "date": "2026-05-12",
                        "kind": "watch",
                        "detail": "On watch.",
                    }
                ]
            }
        return {
            "funded_ratio": 0.75,
            "assumed_return": 0.068,
            "fiscal_year": 2025,
            "allocation": [],
        }


class _StubDiscoverer:
    def discover(self, query, allowed_domains):
        # the two query-based descriptors (acfr, news) resolve to these URLs
        if "report" in query.lower() or "funded" in query.lower():
            return [
                SearchResult(url="https://www.calpers.ca.gov/acfr-2025", title="ACFR")
            ]
        return [
            SearchResult(url="https://www.pionline.com/calpers-watch", title="news")
        ]


def _seed(tmp_path):
    urls = {
        "https://publicplansdata.org/public-plans-database/download-data/": FetchedDoc.from_text(
            "https://publicplansdata.org/public-plans-database/download-data/",
            date(2026, 6, 1),
            "application/json",
            _PPD,
        ),
        "https://www.calpers.ca.gov/acfr-2025": FetchedDoc.from_text(
            "https://www.calpers.ca.gov/acfr-2025",
            date(2026, 6, 1),
            "text/plain",
            _ACFR,
        ),
        "https://www.calpers.ca.gov/page/about/board": FetchedDoc.from_text(
            "https://www.calpers.ca.gov/page/about/board",
            date(2026, 6, 1),
            "text/html",
            _BOARD,
        ),
        "https://www.pionline.com/calpers-watch": FetchedDoc.from_text(
            "https://www.pionline.com/calpers-watch",
            date(2026, 6, 1),
            "text/html",
            _NEWS,
        ),
    }
    fetcher = RecordingFetcher(_StubFetcher(urls), tmp_path)
    disc = RecordingDiscoverer(_StubDiscoverer(), tmp_path)
    llm = RecordingLlmExtractor(_RouterLlm(), tmp_path)
    ingest_client(
        "CALPERS",
        fetcher,
        disc,
        llm,
        captured_at=date(2026, 6, 1),
        synthetic_dir=DATA / "synthetic",
    )


def test_pipeline_replays_to_a_grounded_snapshot(tmp_path):
    _seed(tmp_path)  # record cassettes once
    snap = ingest_client(
        "CALPERS",
        ReplayFetcher(tmp_path),
        ReplayDiscoverer(tmp_path),
        ReplayLlmExtractor(tmp_path),
        captured_at=date(2026, 6, 1),
        synthetic_dir=DATA / "synthetic",
    )
    assert snap.institution.funded_ratio == 0.75
    assert snap.institution.provenance.kind == "public"
    assert any(s.id == "SEAT-CIO" for s in snap.seats)
    assert any(a.kind == "watch" for a in snap.actions)
    # synthetic merged + A1 brief works
    from app.contract.insight import build_brief
    from app.data.repository import Repository

    brief = build_brief(snap, Repository({"CALPERS": snap}), date(2026, 6, 4))
    assert "62" in " ".join(u.insight for u in brief.sections.get("portfolio", []))
