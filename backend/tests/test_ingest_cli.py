import json
from datetime import date
from pathlib import Path

from app.ingest.cli import main
from app.ingest.discover import RecordingDiscoverer, SearchResult
from app.ingest.extract.llm_port import RecordingLlmExtractor
from app.ingest.fetch import RecordingFetcher
from app.ingest.models import FetchedDoc

DATA = Path(__file__).resolve().parents[1] / "data"


_PPD_SCALARS = '[{"status": "OK"}, {"ppd_id": "9", "fy": "2023", "ActFundedRatio_GASB": "0.75", "InvestmentReturnAssumption_GASB": "0.068", "MktAssets_net": "464578.144"}]'
_PPD_ALLOC = '[{"status": "OK"}, {"ppd_id": "9", "fy": "2022", "EQTotal_Actl": "0.43"}]'


class _StubFetcher:
    def fetch(self, url):
        if "QVariables" in url:
            ct, body = "application/json", _PPD_SCALARS
        elif "QDataSet" in url:
            ct, body = "application/json", _PPD_ALLOC
        elif "acfr" in url:
            ct, body = "text/plain", "funded ratio 75 percent"
        elif "board-members" in url or "senior-team" in url:
            ct, body = "text/html", "<h3>CIO</h3>"
        else:
            ct, body = "text/html", "on watch"
        return FetchedDoc.from_text(url, date(2026, 6, 1), ct, body)


class _StubDisc:
    def discover(self, query, allowed_domains):
        acfr = "report" in query.lower() or "funded" in query.lower()
        url = (
            "https://www.calpers.ca.gov/acfr-2025"
            if acfr
            else "https://www.pionline.com/calpers-watch"
        )
        return [SearchResult(url=url, title="x")]


class _RouterLlm:
    def extract(self, system, user):
        s = system.lower()
        if "seat" in s:
            return {
                "seats": [
                    {"id": "SEAT-CIO", "title": "CIO", "decides": "x", "priorities": []}
                ]
            }
        if "action" in s:
            return {"actions": [{"id": "ACT-1", "kind": "watch", "detail": "on watch"}]}
        return {
            "funded_ratio": 0.75,
            "assumed_return": 0.068,
            "fiscal_year": 2025,
            "allocation": [],
        }


def _seed(cass: Path):
    # seed cassettes by running the pipeline once through recording adapters
    from app.ingest.pipeline import ingest_client

    ingest_client(
        "CALPERS",
        RecordingFetcher(_StubFetcher(), cass),
        RecordingDiscoverer(_StubDisc(), cass),
        RecordingLlmExtractor(_RouterLlm(), cass),
        captured_at=date(2026, 6, 1),
        synthetic_dir=DATA / "synthetic",
    )


def test_cli_writes_candidate_then_commits(tmp_path, capsys):
    cass = tmp_path / "cass"
    cass.mkdir()
    _seed(cass)
    out_dir = tmp_path / "out"

    rc = main(["CALPERS", "--cassettes", str(cass), "--out-dir", str(out_dir)])
    assert rc == 0
    candidate = out_dir / "candidates" / "CALPERS.json"
    assert candidate.exists()
    assert json.loads(candidate.read_text())["institution"]["funded_ratio"] == 0.75
    assert not (out_dir / "snapshots" / "CALPERS.json").exists()  # no --commit
    summary = capsys.readouterr().out
    assert "CALPERS" in summary

    rc = main(
        ["CALPERS", "--cassettes", str(cass), "--out-dir", str(out_dir), "--commit"]
    )
    assert rc == 0
    assert (out_dir / "snapshots" / "CALPERS.json").exists()
