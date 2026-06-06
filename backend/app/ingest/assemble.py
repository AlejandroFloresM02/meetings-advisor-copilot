"""Assemble the ingested public layer + the authored synthetic layer into a
validated A1 Snapshot (spec §7)."""

from __future__ import annotations

import datetime

from app.data.snapshot import Snapshot
from app.domain.models import (
    CGMandate,
    GovernanceSeat,
    Institution,
    Interaction,
    InvestmentAction,
    Meeting,
    Opportunity,
    Person,
    RelationshipMeta,
)
from app.ingest.models import InstitutionFacts
from app.ingest.sources import client_identity


def merge_institution_facts(facts: list[InstitutionFacts]) -> InstitutionFacts:
    """Coalesce facts; earlier entries win, later ones fill gaps."""
    if not facts:
        raise ValueError("no institution facts to merge")
    merged = facts[0].model_copy(deep=True)
    for f in facts[1:]:
        for field in (
            "funded_ratio",
            "assumed_return",
            "plan_assets_mm",
            "fiscal_year",
        ):
            if getattr(merged, field) is None:
                setattr(merged, field, getattr(f, field))
        if not merged.allocation and f.allocation:
            merged.allocation = list(f.allocation)
    return merged


def _check_public(prov) -> None:
    if prov.kind == "public" and (prov.url is None or prov.fetched_at is None):
        raise ValueError(f"public fact missing provenance url/fetched_at: {prov!r}")


def assemble(
    client_id: str,
    captured_at: datetime.date,
    facts: list[InstitutionFacts],
    seats: list[GovernanceSeat],
    actions: list[InvestmentAction],
    synthetic: dict,
) -> Snapshot:
    merged = merge_institution_facts(facts)
    _check_public(merged.provenance)
    for s in seats:
        _check_public(s.provenance)
    for a in actions:
        _check_public(a.provenance)

    ident = client_identity(client_id)
    institution = Institution(
        id=ident["id"],
        name=ident["name"],
        type=ident["type"],
        plan_assets_mm=merged.plan_assets_mm,
        fiscal_year=merged.fiscal_year,
        funded_ratio=merged.funded_ratio,
        assumed_return=merged.assumed_return,
        allocation=merged.allocation,
        policy_benchmark=ident.get("policy_benchmark"),
        provenance=merged.provenance,
    )

    rel = synthetic.get("relationship")
    return Snapshot(
        client_id=client_id,
        captured_at=captured_at,
        institution=institution,
        seats=seats,
        people=[Person.model_validate(p) for p in synthetic.get("people", [])],
        actions=actions,
        mandates=[CGMandate.model_validate(m) for m in synthetic.get("mandates", [])],
        pipeline=[Opportunity.model_validate(o) for o in synthetic.get("pipeline", [])],
        relationship=RelationshipMeta.model_validate(rel) if rel else None,
        interactions=[
            Interaction.model_validate(i) for i in synthetic.get("interactions", [])
        ],
        meetings=[Meeting.model_validate(m) for m in synthetic.get("meetings", [])],
    )
