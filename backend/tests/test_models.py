from datetime import date

import pydantic
import pytest

from app.domain.models import (
    AllocationSlice,
    Brief,
    Evidence,
    InsightUnit,
    Institution,
    Meeting,
)
from app.provenance import Provenance


def test_provenance_requires_kind():
    p = Provenance(
        kind="public", url="https://example.gov/acfr", fetched_at=date(2026, 6, 1)
    )
    assert p.kind == "public"
    assert p.url.endswith("acfr")


def test_institution_holds_allocation_and_provenance():
    inst = Institution(
        id="CALPERS",
        name="CalPERS",
        type="public_pension",
        plan_assets_mm=502000.0,
        fiscal_year=2025,
        funded_ratio=0.75,
        assumed_return=0.068,
        allocation=[
            AllocationSlice(
                asset_class="Fixed Income", target_pct=30.0, actual_pct=28.0
            )
        ],
        policy_benchmark="CalPERS Policy Benchmark",
        provenance=Provenance(kind="public", url="https://calpers.ca.gov"),
    )
    assert inst.allocation[0].asset_class == "Fixed Income"
    assert inst.provenance.kind == "public"


def test_meeting_scenario_is_constrained():
    m = Meeting(
        id="MTG-1",
        date=date(2026, 6, 5),
        purpose="Review",
        objective="Defend mandate",
        scenario="portfolio_review",
        seat_ids=["SEAT-CIO"],
        provenance=Provenance(kind="synthetic"),
    )
    assert m.scenario == "portfolio_review"
    with pytest.raises(pydantic.ValidationError):
        Meeting(
            id="MTG-2",
            date=date(2026, 6, 5),
            purpose="x",
            objective=None,
            scenario="bogus",
            seat_ids=[],
            provenance=Provenance(kind="synthetic"),
        )


def test_insight_unit_and_brief_compose():
    u = InsightUnit(
        insight="Fee pressure threatens the Core Plus mandate.",
        why_now="The IC opened a cost review.",
        evidence=[
            Evidence(text="Mandate fee 38bps", provenance=Provenance(kind="synthetic"))
        ],
        play="Offer the SMA breakpoint.",
        severity="high",
        score=0.8,
    )
    b = Brief(
        client_id="CALPERS",
        scenario="portfolio_review",
        bluf="Defend the mandate.",
        sections={"risks": [u]},
        meta={"generated_at": "2026-06-04"},
    )
    assert b.sections["risks"][0].insight.startswith("Fee pressure")
    assert b.bluf
