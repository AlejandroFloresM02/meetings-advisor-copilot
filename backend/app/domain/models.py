"""V2 entity taxonomy (spec §5) + content-contract types (spec §9).

Every entity carries a Provenance tag. Numbers that must be citable are carried
as Metric/Evidence so the guard (app/guard.py) can verify them.

Date-typed fields use the qualified ``datetime.date`` rather than a bare
``date`` import: several entities have a field literally named ``date``, and
under ``from __future__ import annotations`` that field name would shadow a bare
``date`` type during pydantic's annotation evaluation.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.provenance import Provenance


# ---- value objects ---------------------------------------------------------
class Metric(BaseModel):
    key: str
    value: float
    unit: str | None = None  # "%", "bps", "$mm", "ratio"
    as_of: datetime.date | None = None
    provenance: Provenance


class Evidence(BaseModel):
    text: str
    provenance: Provenance


class InsightUnit(BaseModel):
    insight: str
    why_now: str
    evidence: list[Evidence] = Field(default_factory=list)
    play: str | None = None
    freshness: Literal["frozen", "live"] = "frozen"
    severity: str | None = None
    score: float | None = None


class Brief(BaseModel):
    client_id: str
    scenario: str
    bluf: str
    sections: dict[str, list[InsightUnit]] = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


# ---- entities --------------------------------------------------------------
class AllocationSlice(BaseModel):
    asset_class: str
    target_pct: float | None = None
    actual_pct: float | None = None


class Institution(BaseModel):
    id: str
    name: str
    type: str
    plan_assets_mm: float | None = None
    fiscal_year: int | None = None
    funded_ratio: float | None = None
    assumed_return: float | None = None
    allocation: list[AllocationSlice] = Field(default_factory=list)
    policy_benchmark: str | None = None
    provenance: Provenance


class GovernanceSeat(BaseModel):
    id: str
    title: str
    remit: str | None = None
    committee: str | None = None
    decides: str | None = None
    priorities: list[str] = Field(default_factory=list)
    provenance: Provenance


class Person(BaseModel):
    id: str
    name: str  # imagined persona — no real PII (spec §8)
    seat_id: str
    background: str | None = None
    provenance: Provenance


class CGMandate(BaseModel):
    id: str
    strategy: str
    vehicle: str | None = None
    size_mm: float = 0.0
    fee_bps: float | None = None
    inception: datetime.date | None = None
    net_excess_bps: float | None = None
    information_ratio: float | None = None
    down_capture: float | None = None
    benchmark: str | None = None
    provenance: Provenance


class Opportunity(BaseModel):
    id: str
    strategy: str
    size_mm: float = 0.0
    stage: str
    probability: float = 0.0
    expected_close: datetime.date | None = None
    owner: str | None = None
    provenance: Provenance


class RelationshipMeta(BaseModel):
    rm: str | None = None
    tier: str | None = None
    consultant: str | None = None
    status: str | None = None
    client_since: int | None = None
    provenance: Provenance


class InvestmentAction(BaseModel):
    id: str
    date: datetime.date | None = None
    kind: str  # "hire" | "terminate" | "search" | "watch"
    manager: str | None = None
    asset_class: str | None = None
    detail: str | None = None
    provenance: Provenance


class Interaction(BaseModel):
    id: str
    date: datetime.date | None = None
    kind: str
    summary: str
    open_action_items: list[str] = Field(default_factory=list)
    provenance: Provenance


class Meeting(BaseModel):
    id: str
    date: datetime.date
    purpose: str
    objective: str | None = None
    scenario: Literal[
        "portfolio_review", "finals", "at_risk_save", "relationship_review"
    ]
    seat_ids: list[str] = Field(default_factory=list)
    provenance: Provenance


# ---- derived outputs -------------------------------------------------------
class RiskFlag(BaseModel):
    key: str
    title: str
    severity: str
    score: float
    evidence: str
    provenance: Provenance


class CostEffectiveness(BaseModel):
    net_value_added_bps: float | None = None
    excess_cost_bps: float | None = None
    verdict: str
    evidence: str


class Delta(BaseModel):
    field: str
    before: Any = None
    after: Any = None
    direction: str  # "up" | "down" | "changed"
    summary: str
