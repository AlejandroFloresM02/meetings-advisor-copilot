from datetime import date

from app.contract.insight import build_brief
from app.guard import unit_supported


def test_build_brief_is_grounded_and_scenario_aware(repo, calpers):
    brief = build_brief(calpers, repo, date(2026, 6, 4))
    assert brief.client_id == "CALPERS"
    assert brief.scenario == "portfolio_review"
    assert brief.bluf  # non-empty bottom line
    # core sections present
    assert {"risks", "the_room", "portfolio"} <= set(brief.sections)
    # every emitted insight unit passes the guard (numbers trace to evidence)
    all_units = [u for units in brief.sections.values() for u in units]
    assert all_units
    assert all(unit_supported(u) for u in all_units)
    # the room reflects the attending seats (2 seats -> 2 people units)
    assert len(brief.sections["the_room"]) == 2
    # portfolio cites the mandate's net excess (62) and fee (38)
    port_text = " ".join(u.insight + u.why_now for u in brief.sections["portfolio"])
    assert "62" in port_text
    assert "38" in port_text


def test_build_brief_meta_marks_synthetic():
    # meta should flag that the CG layer is synthetic (spec §8 labeling)
    from app.config import SNAPSHOTS_DIR
    from app.data.repository import load_repository

    r = load_repository(SNAPSHOTS_DIR)
    brief = build_brief(r.get("CALPERS"), r, date(2026, 6, 4))
    assert brief.meta.get("contains_synthetic") is True
    assert brief.meta.get("disclaimer")
