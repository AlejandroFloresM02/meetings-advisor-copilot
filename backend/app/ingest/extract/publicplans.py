"""Deterministic PublicPlansData (PPD) API extractor (spec §6); no LLM.

The PPD REST API (publicplansdata.org/api/) returns a JSON *array*: element 0 is
a status/metadata header, elements 1.. are data records whose values are all
JSON strings. The QVariables "national data" join repeats rows per fiscal year
with many nulls, so we take the latest fiscal year that has data and coalesce
each field across that year's rows. Two endpoints feed this extractor and each
yields a partial InstitutionFacts that assemble.merge coalesces:
  - QVariables  -> scalars (funded ratio, assumed return, assets, fiscal year)
  - QDataSet=pensioninvestmentperformance -> actual asset allocation (*_Actl)
"""

from __future__ import annotations

import json

from app.domain.models import AllocationSlice
from app.ingest.models import FetchedDoc, InstitutionFacts
from app.provenance import Provenance

# PPD actual-allocation columns (0-1 fractions) -> human asset-class labels.
_ALLOCATION = {
    "EQTotal_Actl": "Public Equity",
    "FITotal_Actl": "Fixed Income",
    "RETotal_Actl": "Real Estate",
    "PETotal_Actl": "Private Equity",
    "AltMiscTotal_Actl": "Alternatives/Misc",
    "HFTotal_Actl": "Hedge Funds",
    "COMDTotal_Actl": "Commodities",
    "CashTotal_Actl": "Cash",
    "OtherTotal_Actl": "Other",
}
# scalar columns that mark a record as "populated" (besides fy).
_SCALAR_KEYS = (
    "ActFundedRatio_GASB",
    "InvestmentReturnAssumption_GASB",
    "MktAssets_net",
)


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _records(text: str) -> list[dict]:
    """PPD payload -> data records (drop the metadata header; honor ERROR status)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list) or not data:
        return []
    head = data[0]
    if isinstance(head, dict) and head.get("status") == "ERROR":
        return []
    return [r for r in data[1:] if isinstance(r, dict)]


def _is_populated(rec: dict) -> bool:
    return any(_num(rec.get(k)) is not None for k in (*_SCALAR_KEYS, *_ALLOCATION))


def _latest_fy(records: list[dict]) -> float | None:
    fys = [_num(r.get("fy")) for r in records if _is_populated(r)]
    fys = [fy for fy in fys if fy is not None]
    return max(fys) if fys else None


def _coalesce(records: list[dict], fy: float, field: str) -> float | None:
    """First non-null value of `field` among the rows for fiscal year `fy`."""
    for r in records:
        if _num(r.get("fy")) == fy and (v := _num(r.get(field))) is not None:
            return v
    return None


def extract(doc: FetchedDoc) -> InstitutionFacts:
    records = _records(doc.text())
    prov = Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at)
    fy = _latest_fy(records)
    if fy is None:
        return InstitutionFacts(provenance=prov)

    def g(field: str) -> float | None:
        return _coalesce(records, fy, field)

    allocation = [
        AllocationSlice(asset_class=label, actual_pct=round(pct * 100, 2))
        for field, label in _ALLOCATION.items()
        if (pct := g(field)) is not None
    ]
    # MktAssets_net is reported in thousands of dollars -> convert to $mm.
    assets = g("MktAssets_net")
    return InstitutionFacts(
        funded_ratio=g("ActFundedRatio_GASB"),
        assumed_return=g("InvestmentReturnAssumption_GASB"),
        plan_assets_mm=assets / 1000 if assets is not None else None,
        fiscal_year=int(fy),
        allocation=allocation,
        provenance=prov,
    )
