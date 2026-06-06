"""The committed per-client snapshot (spec §4) — the trusted corpus the runtime reads."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

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


class Snapshot(BaseModel):
    client_id: str
    captured_at: date
    institution: Institution
    seats: list[GovernanceSeat] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)
    actions: list[InvestmentAction] = Field(default_factory=list)
    mandates: list[CGMandate] = Field(default_factory=list)
    pipeline: list[Opportunity] = Field(default_factory=list)
    relationship: RelationshipMeta | None = None
    interactions: list[Interaction] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)


def load_snapshot(path: Path) -> Snapshot:
    return Snapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_all_snapshots(directory: Path) -> dict[str, Snapshot]:
    out: dict[str, Snapshot] = {}
    for fp in sorted(Path(directory).glob("*.json")):
        snap = load_snapshot(fp)
        out[snap.client_id] = snap
    return out
