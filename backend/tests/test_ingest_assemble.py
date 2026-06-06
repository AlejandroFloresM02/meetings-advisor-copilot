import json
from datetime import date
from pathlib import Path

import pytest

from app.domain.models import AllocationSlice, GovernanceSeat, InvestmentAction
from app.ingest.assemble import assemble, merge_institution_facts
from app.ingest.models import InstitutionFacts
from app.provenance import Provenance

SYNTH = json.loads(
    Path(__file__)
    .resolve()
    .parents[1]
    .joinpath("data/synthetic/CALPERS.json")
    .read_text()
)

PUB = Provenance(
    kind="public", url="https://publicplansdata.org/x", fetched_at=date(2026, 6, 1)
)


def _ppd():
    return InstitutionFacts(
        funded_ratio=0.75,
        plan_assets_mm=502000.0,
        allocation=[
            AllocationSlice(
                asset_class="Fixed Income", target_pct=30.0, actual_pct=28.0
            )
        ],
        provenance=PUB,
    )


def _acfr():
    return InstitutionFacts(assumed_return=0.068, fiscal_year=2025, provenance=PUB)


def _seat():
    return GovernanceSeat(
        id="SEAT-CIO",
        title="Chief Investment Officer",
        decides="Allocation",
        priorities=["cost"],
        provenance=PUB,
    )


def _action():
    return InvestmentAction(
        id="ACT-1",
        date=date(2026, 5, 12),
        kind="watch",
        detail="On watch.",
        provenance=PUB,
    )


def test_merge_prefers_earlier_facts_but_fills_gaps():
    merged = merge_institution_facts([_ppd(), _acfr()])
    assert merged.funded_ratio == 0.75  # from PPD
    assert merged.assumed_return == 0.068  # filled from ACFR
    assert merged.fiscal_year == 2025
    assert merged.allocation[0].asset_class == "Fixed Income"


def test_assemble_builds_a_valid_snapshot():
    snap = assemble(
        "CALPERS", date(2026, 6, 1), [_ppd(), _acfr()], [_seat()], [_action()], SYNTH
    )
    assert snap.client_id == "CALPERS"
    assert snap.institution.name == "CalPERS"
    assert snap.institution.funded_ratio == 0.75
    assert snap.institution.provenance.kind == "public"
    # synthetic layer merged
    assert snap.mandates[0].fee_bps == 38.0
    assert snap.meetings[0].scenario == "portfolio_review"
    # A1's brief assembler still works on the result
    from app.contract.insight import build_brief
    from app.data.repository import Repository
    from app.data.snapshot import Snapshot

    assert isinstance(snap, Snapshot)
    brief = build_brief(snap, Repository({"CALPERS": snap}), date(2026, 6, 4))
    assert brief.scenario == "portfolio_review"


def test_assemble_rejects_unsourced_public_fact():
    bad = InstitutionFacts(
        funded_ratio=0.75, provenance=Provenance(kind="public")
    )  # no url
    with pytest.raises(ValueError, match="provenance"):
        assemble("CALPERS", date(2026, 6, 1), [bad], [_seat()], [_action()], SYNTH)
