"""News extractor (spec §6): HTML text + LLM -> list[InvestmentAction]
(public provenance)."""

from __future__ import annotations

import datetime

from app.domain.models import InvestmentAction
from app.ingest.extract.board import html_to_text
from app.ingest.extract.llm_port import LlmExtractor
from app.ingest.models import FetchedDoc
from app.provenance import Provenance

_SYSTEM = (
    "You extract a US public pension's investment actions (manager hires, "
    "terminations, searches, watch-list placements) from news/press text. Return "
    "JSON {actions: [{id, date: YYYY-MM-DD, kind, manager, asset_class, detail}]}. "
    "kind is one of hire|terminate|search|watch. Only actions stated in the text."
)


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def extract(doc: FetchedDoc, llm: LlmExtractor) -> list[InvestmentAction]:
    text = html_to_text(doc.text())
    data = llm.extract(_SYSTEM, text[:12000])
    prov = Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at)
    actions = []
    for a in data.get("actions") or []:
        if not isinstance(a, dict) or not a.get("kind"):
            continue
        actions.append(
            InvestmentAction(
                id=a.get("id") or f"ACT-{len(actions) + 1}",
                date=_parse_date(a.get("date")),
                kind=a["kind"],
                manager=a.get("manager"),
                asset_class=a.get("asset_class"),
                detail=a.get("detail"),
                provenance=prov,
            )
        )
    return actions
