"""Board/staff extractor (spec §6): HTML text (selectolax) + LLM ->
list[GovernanceSeat] (public provenance)."""

from __future__ import annotations

from app.domain.models import GovernanceSeat
from app.ingest.extract.llm_port import LlmExtractor
from app.ingest.models import FetchedDoc
from app.provenance import Provenance

_SYSTEM = (
    "You extract governance seats (committee roles) of a US public pension from "
    "its board/staff page text. Return JSON {seats: [{id, title, remit, committee, "
    "decides, priorities: [str]}]}. id is an uppercase slug like SEAT-CIO. "
    "Only include seats clearly named in the text; do not invent people."
)


def html_to_text(html: str) -> str:
    from selectolax.parser import HTMLParser

    tree = HTMLParser(html)
    for tag in tree.css("script, style"):
        tag.decompose()
    body = tree.body or tree.root
    return " ".join(body.text(separator=" ", strip=True).split()) if body else ""


def extract(doc: FetchedDoc, llm: LlmExtractor) -> list[GovernanceSeat]:
    text = html_to_text(doc.text())
    data = llm.extract(_SYSTEM, text[:12000])
    prov = Provenance(kind="public", url=doc.url, fetched_at=doc.fetched_at)
    seats = []
    for s in data.get("seats") or []:
        if not isinstance(s, dict) or not s.get("title"):
            continue
        seats.append(
            GovernanceSeat(
                id=s.get("id") or s["title"].upper().replace(" ", "-"),
                title=s["title"],
                remit=s.get("remit"),
                committee=s.get("committee"),
                decides=s.get("decides"),
                priorities=list(s.get("priorities") or []),
                provenance=prov,
            )
        )
    return seats
