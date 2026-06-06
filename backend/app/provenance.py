"""Provenance tag attached to every fact in the V2 data model."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

ProvenanceKind = Literal["public", "cg_house_view", "synthetic", "derived"]


class Provenance(BaseModel):
    kind: ProvenanceKind
    url: str | None = None
    fetched_at: date | None = None
    note: str | None = None
