"""Ingestion orchestrator (spec §4): registry -> discover/fetch -> extract ->
assemble -> validated Snapshot."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from app.data.snapshot import Snapshot
from app.ingest.assemble import assemble
from app.ingest.discover import Discoverer
from app.ingest.extract import acfr, board, news, publicplans
from app.ingest.extract.llm_port import LlmExtractor
from app.ingest.fetch import Fetcher
from app.ingest.models import FetchedDoc, SourceDescriptor
from app.ingest.sources import sources_for


def load_synthetic(client_id: str, directory: Path) -> dict:
    return json.loads(
        (Path(directory) / f"{client_id}.json").read_text(encoding="utf-8")
    )


def _resolve_url(sd: SourceDescriptor, discoverer: Discoverer) -> str:
    if sd.url:
        return sd.url
    results = discoverer.discover(sd.query or "", sd.domains)
    if not results:
        raise LookupError(f"discover found nothing for {sd.query!r}")
    return results[0].url


def ingest_client(
    client_id: str,
    fetcher: Fetcher,
    discoverer: Discoverer,
    llm: LlmExtractor,
    *,
    captured_at: datetime.date,
    synthetic_dir: Path,
) -> Snapshot:
    facts = []
    seats = []
    actions = []
    for sd in sources_for(client_id):
        doc: FetchedDoc = fetcher.fetch(_resolve_url(sd, discoverer))
        if sd.extractor == "publicplans":
            facts.append(publicplans.extract(doc))
        elif sd.extractor == "acfr":
            facts.append(acfr.extract(doc, llm))
        elif sd.extractor == "board":
            seats.extend(board.extract(doc, llm))
        elif sd.extractor == "news":
            actions.extend(news.extract(doc, llm))
        else:  # pragma: no cover - registry guards this
            raise ValueError(f"unknown extractor {sd.extractor!r}")

    synthetic = load_synthetic(client_id, synthetic_dir)
    return assemble(client_id, captured_at, facts, seats, actions, synthetic)
