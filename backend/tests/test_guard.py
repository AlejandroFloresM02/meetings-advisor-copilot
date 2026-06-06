from app.domain.models import Evidence, InsightUnit
from app.guard import extract_numbers, guard_units, unit_supported
from app.provenance import Provenance


def test_extract_numbers_strips_punctuation():
    assert {"946", "2", "80"} <= extract_numbers("~$946mm across 2 mandates at 80%")


def test_unit_supported_requires_numbers_in_evidence():
    ev = [
        Evidence(
            text="Mandate fee 38bps; net excess 62bps",
            provenance=Provenance(kind="synthetic"),
        )
    ]
    ok = InsightUnit(
        insight="Fee is 38bps for 62bps of value", why_now="x", evidence=ev
    )
    bad = InsightUnit(insight="Fee is 99bps", why_now="x", evidence=ev)  # 99 not in ev
    assert unit_supported(ok)
    assert not unit_supported(bad)


def test_unit_with_no_evidence_is_dropped():
    naked = InsightUnit(insight="Worth $700mm", why_now="x", evidence=[])
    assert not unit_supported(naked)


def test_guard_units_filters():
    ev = [Evidence(text="38bps", provenance=Provenance(kind="synthetic"))]
    kept = guard_units(
        [
            InsightUnit(insight="Fee 38bps", why_now="x", evidence=ev),
            InsightUnit(insight="Fee 99bps", why_now="x", evidence=ev),
        ]
    )
    assert len(kept) == 1
    assert "38" in kept[0].insight
