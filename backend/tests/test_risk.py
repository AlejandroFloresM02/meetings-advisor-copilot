from datetime import date

from app.derived.risk import compute_risk, severity_band


def test_severity_bands():
    assert severity_band(0.9) == "high"
    assert severity_band(0.5) == "medium"
    assert severity_band(0.1) == "low"


def test_calpers_flags_are_grounded(repo, calpers):
    flags = compute_risk(calpers, repo, date(2026, 6, 4))
    keys = {f.key for f in flags}
    # underfunded (0.75) -> funded_status risk; manager on watch -> manager_watch
    assert {"funded_status", "manager_watch", "allocation_gap"} <= keys
    funded = next(f for f in flags if f.key == "funded_status")
    assert funded.severity in {"high", "medium"}
    assert "75" in funded.evidence  # cites the funded ratio
    assert funded.provenance.kind == "derived"
    # private-credit underweight (1.5 vs 4.0 target) should surface
    gap = next(f for f in flags if f.key == "allocation_gap")
    assert "Private Credit" in gap.evidence
    # flags are sorted by score desc
    assert flags == sorted(flags, key=lambda f: f.score, reverse=True)
