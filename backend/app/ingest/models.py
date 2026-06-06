"""Value objects for the ingestion pipeline (spec §4)."""

from __future__ import annotations

import base64
import datetime

from pydantic import BaseModel, Field

from app.domain.models import AllocationSlice
from app.provenance import Provenance


class FetchedDoc(BaseModel):
    """A fetched document with its source URL and fetch timestamp (provenance)."""

    url: str
    fetched_at: datetime.date
    content_type: str
    body_b64: str  # base64 of the raw bytes (uniform for HTML + PDF)

    def raw(self) -> bytes:
        return base64.b64decode(self.body_b64)

    def text(self, encoding: str = "utf-8") -> str:
        return self.raw().decode(encoding, errors="replace")

    @classmethod
    def from_bytes(
        cls, url: str, fetched_at: datetime.date, content_type: str, body: bytes
    ) -> FetchedDoc:
        return cls(
            url=url,
            fetched_at=fetched_at,
            content_type=content_type,
            body_b64=base64.b64encode(body).decode("ascii"),
        )

    @classmethod
    def from_text(
        cls, url: str, fetched_at: datetime.date, content_type: str, text: str
    ) -> FetchedDoc:
        return cls.from_bytes(url, fetched_at, content_type, text.encode("utf-8"))


class SourceDescriptor(BaseModel):
    """One allowlisted source for one fact group of one client (spec §5)."""

    client_id: str
    fact_group: str  # "institution" | "seats" | "actions"
    extractor: str  # "publicplans" | "acfr" | "board" | "news"
    url: str | None = None  # canonical URL (discover bypassed when set)
    query: str | None = None  # SearXNG query (when url is unknown)
    domains: list[str] = Field(default_factory=list)  # allowlist for discover


class InstitutionFacts(BaseModel):
    """Partial Institution fields a public source yields, with provenance."""

    funded_ratio: float | None = None
    assumed_return: float | None = None
    plan_assets_mm: float | None = None
    fiscal_year: int | None = None
    allocation: list[AllocationSlice] = Field(default_factory=list)
    provenance: Provenance
