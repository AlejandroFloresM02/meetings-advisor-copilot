from datetime import date

from app.ingest.extract import publicplans
from app.ingest.models import FetchedDoc

# PPD REST API shape: a JSON array whose first element is a status/metadata
# header and the rest are data records (all values are JSON strings).
_SCALARS = (
    "["
    '{"status": "OK", "recordcount": 2, "date": "2026-06-07"},'
    '{"ppd_id": "9", "PlanName": "California PERF", "fy": "2021",'
    ' "ActFundedRatio_GASB": "0.75", "InvestmentReturnAssumption_GASB": "0.07",'
    ' "MktAssets_net": "440000.0"},'
    '{"ppd_id": "9", "PlanName": "California PERF", "fy": "2023",'
    ' "ActFundedRatio_GASB": "0.71313", "InvestmentReturnAssumption_GASB": "0.068",'
    ' "MktAssets_net": "464578144.0"}'  # PPD reports assets in thousands
    "]"
)

_ALLOCATION = (
    "["
    '{"status": "OK", "recordcount": 1},'
    '{"ppd_id": "9", "fy": "2022", "EQTotal_Actl": "0.43", "FITotal_Actl": "0.25",'
    ' "RETotal_Actl": "0.16", "PETotal_Actl": "0.12", "CashTotal_Actl": "0.04"}'
    "]"
)

_ERROR = (
    '[{"status": "ERROR", "recordcount": 0}, {"Error": "Unknown variable \'Foo\'"}]'
)


def _doc(payload: str) -> FetchedDoc:
    return FetchedDoc.from_text(
        "https://publicplansdata.org/api/?q=QVariables&filterppdid=9",
        date(2026, 6, 1),
        "application/json",
        payload,
    )


def test_publicplans_scalars_picks_latest_populated_year():
    facts = publicplans.extract(_doc(_SCALARS))
    assert facts.fiscal_year == 2023  # latest, not 2021
    assert facts.funded_ratio == 0.71313
    assert facts.assumed_return == 0.068
    assert facts.plan_assets_mm == 464578.144
    assert facts.allocation == []  # scalars call carries no allocation
    assert facts.provenance.kind == "public"
    assert facts.provenance.fetched_at == date(2026, 6, 1)


def test_publicplans_allocation_dataset_maps_actual_pct():
    facts = publicplans.extract(_doc(_ALLOCATION))
    by_class = {a.asset_class: a.actual_pct for a in facts.allocation}
    assert by_class["Public Equity"] == 43.0  # 0.43 fraction -> 43.0%
    assert by_class["Fixed Income"] == 25.0
    assert by_class["Private Equity"] == 12.0
    assert facts.funded_ratio is None  # allocation call carries no scalars


def test_publicplans_error_payload_yields_empty_but_sourced_facts():
    facts = publicplans.extract(_doc(_ERROR))
    assert facts.funded_ratio is None
    assert facts.allocation == []
    assert facts.provenance.kind == "public"  # still provenance-tagged
