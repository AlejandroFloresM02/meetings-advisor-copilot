from datetime import date

from app.risk.engine import compute_risk, severity_band


def test_severity_bands():
    assert severity_band(0.9) == "high"
    assert severity_band(0.5) == "medium"
    assert severity_band(0.1) == "low"


def test_calderon_flags_no_decision_maker_and_prospect(repo):
    res = compute_risk(repo, "ACC-1002", date(2026, 6, 4))
    keys = {c.key for c in res.components}
    assert {"coverage", "status", "pipeline", "consultant"} <= keys
    coverage = next(c for c in res.components if c.key == "coverage")
    assert coverage.severity == "high"  # no Decision Maker mapped
    assert "Decision Maker" in coverage.evidence
    assert 0.0 <= res.overall <= 1.0


def test_at_risk_account_scores_status_high(repo):
    res = compute_risk(repo, "ACC-1017", date(2026, 6, 4))  # Stonebridge, At Risk
    status = next(c for c in res.components if c.key == "status")
    assert status.severity == "high"
