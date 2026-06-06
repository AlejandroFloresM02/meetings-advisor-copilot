from datetime import date

from app.ingest.extract import publicplans
from app.ingest.models import FetchedDoc

_PPD_JSON = (
    '{"PlanName": "CalPERS", "FundedRatio": 0.75, "ActuarialAssumedInterest": 0.068,'
    ' "TotalPlanAssets_mm": 502000.0, "FiscalYear": 2025,'
    ' "Allocation": [{"asset_class": "Fixed Income", "target_pct": 30.0, "actual_pct": 28.0}]}'
)


def test_publicplans_extracts_institution_facts():
    doc = FetchedDoc.from_text(
        "https://publicplansdata.org/x", date(2026, 6, 1), "application/json", _PPD_JSON
    )
    facts = publicplans.extract(doc)
    assert facts.funded_ratio == 0.75
    assert facts.assumed_return == 0.068
    assert facts.plan_assets_mm == 502000.0
    assert facts.fiscal_year == 2025
    assert facts.allocation[0].asset_class == "Fixed Income"
    # provenance carries the source url + fetch date
    assert facts.provenance.kind == "public"
    assert facts.provenance.url == "https://publicplansdata.org/x"
    assert facts.provenance.fetched_at == date(2026, 6, 1)
