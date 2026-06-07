from datetime import date
from pathlib import Path

from app.ingest.discover import RecordingDiscoverer, ReplayDiscoverer, SearchResult
from app.ingest.extract.llm_port import RecordingLlmExtractor, ReplayLlmExtractor
from app.ingest.fetch import RecordingFetcher, ReplayFetcher
from app.ingest.models import FetchedDoc
from app.ingest.pipeline import ingest_client

DATA = Path(__file__).resolve().parents[1] / "data"

_PPD_SCALARS = '[{"status": "OK"}, {"ppd_id": "9", "fy": "2023", "ActFundedRatio_GASB": "0.75", "InvestmentReturnAssumption_GASB": "0.068", "MktAssets_net": "464578.144"}]'
_PPD_ALLOC = '[{"status": "OK"}, {"ppd_id": "9", "fy": "2022", "EQTotal_Actl": "0.43", "FITotal_Actl": "0.25"}]'
_BOARD = "<html><body><h3>Chief Investment Officer</h3></body></html>"
_NEWS = "<html><body>CalPERS placed a manager on watch.</body></html>"
_ACFR = "CalPERS ACFR FY2025 funded ratio 75 percent."


def _doc(url, ct, body):
    return FetchedDoc.from_text(url, date(2026, 6, 1), ct, body)


class _StubFetcher:
    """Canned content keyed by URL shape (decoupled from exact source URLs)."""

    def fetch(self, url):
        if "QVariables" in url:
            return _doc(url, "application/json", _PPD_SCALARS)
        if "QDataSet" in url:
            return _doc(url, "application/json", _PPD_ALLOC)
        if "acfr" in url:
            return _doc(url, "text/plain", _ACFR)
        if "board-members" in url or "senior-team" in url:
            return _doc(url, "text/html", _BOARD)
        return _doc(url, "text/html", _NEWS)


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
    fetcher = RecordingFetcher(_StubFetcher(), tmp_path)
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
