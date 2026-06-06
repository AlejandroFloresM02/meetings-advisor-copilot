"""Deterministic Public Plans Database extractor (spec §6). Structured JSON ->
InstitutionFacts; no LLM."""

from __future__ import annotations

import json

from app.domain.models import AllocationSlice
from app.ingest.models import FetchedDoc, InstitutionFacts
from app.provenance import Provenance


def extract(doc: FetchedDoc) -> InstitutionFacts:
    data = json.loads(doc.text())
    allocation = [
        AllocationSlice(
            asset_class=a["asset_class"],
            target_pct=a.get("target_pct"),
            actual_pct=a.get("actual_pct"),
        )
        for a in data.get("Allocation", [])
    ]
    return InstitutionFacts(
        funded_ratio=data.get("FundedRatio"),
        assumed_return=data.get("ActuarialAssumedInterest"),
        plan_assets_mm=data.get("TotalPlanAssets_mm"),
        fiscal_year=data.get("FiscalYear"),
        allocation=allocation,
        provenance=Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at),
    )
