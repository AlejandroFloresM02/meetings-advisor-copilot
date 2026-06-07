"""Deterministic PublicPlansData (PPD) API extractor (spec §6); no LLM.

The PPD REST API (publicplansdata.org/api/) returns a JSON *array*: element 0 is
a status/metadata header, elements 1.. are data records whose values are all
JSON strings. Two endpoints feed this extractor and each yields a partial
InstitutionFacts that assemble.merge coalesces:
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
    keys = (*_SCALAR_KEYS, *_ALLOCATION)
    return any(_num(rec.get(k)) is not None for k in keys)


def extract(doc: FetchedDoc) -> InstitutionFacts:
    records = [r for r in _records(doc.text()) if _is_populated(r)]
    records.sort(key=lambda r: _num(r.get("fy")) or -1, reverse=True)
    rec = records[0] if records else {}

    allocation = [
        AllocationSlice(asset_class=label, actual_pct=round(pct * 100, 2))
        for field, label in _ALLOCATION.items()
        if (pct := _num(rec.get(field))) is not None
    ]

    fy = _num(rec.get("fy"))
    return InstitutionFacts(
        funded_ratio=_num(rec.get("ActFundedRatio_GASB")),
        assumed_return=_num(rec.get("InvestmentReturnAssumption_GASB")),
        plan_assets_mm=_num(rec.get("MktAssets_net")),
        fiscal_year=int(fy) if fy is not None else None,
        allocation=allocation,
        provenance=Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at),
    )
