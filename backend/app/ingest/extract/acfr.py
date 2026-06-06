"""ACFR extractor (spec §6): PDF text (pypdf) + LLM -> InstitutionFacts.

`pdf_to_text` is a thin pypdf wrapper exercised by the live --refresh-fixtures
path; the offline suite tests the extraction logic via text content."""

from __future__ import annotations

import io

from app.domain.models import AllocationSlice
from app.ingest.extract.llm_port import LlmExtractor
from app.ingest.models import FetchedDoc, InstitutionFacts
from app.provenance import Provenance

_SYSTEM = (
    "You extract a US public pension's funded status from its ACFR text. "
    "Return JSON with keys funded_ratio (0-1), assumed_return (0-1), "
    "fiscal_year (int), and allocation (list of {asset_class, target_pct, actual_pct}). "
    "Use null when a value is not stated. Do not invent numbers."
)


def pdf_to_text(body: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(body))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _content_text(doc: FetchedDoc) -> str:
    if "pdf" in doc.content_type.lower():
        return pdf_to_text(doc.raw())
    return doc.text()


def extract(doc: FetchedDoc, llm: LlmExtractor) -> InstitutionFacts:
    text = _content_text(doc)
    data = llm.extract(_SYSTEM, text[:12000])
    allocation = [
        AllocationSlice(
            asset_class=a["asset_class"],
            target_pct=a.get("target_pct"),
            actual_pct=a.get("actual_pct"),
        )
        for a in (data.get("allocation") or [])
        if isinstance(a, dict) and a.get("asset_class")
    ]
    return InstitutionFacts(
        funded_ratio=data.get("funded_ratio"),
        assumed_return=data.get("assumed_return"),
        fiscal_year=data.get("fiscal_year"),
        allocation=allocation,
        provenance=Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at),
    )
