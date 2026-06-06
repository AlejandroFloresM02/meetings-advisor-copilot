"""Ingestion CLI (spec §4): `python -m app.ingest CALPERS [--commit] ...`.

Replay (default) reads committed cassettes; --refresh-fixtures records live from
SearXNG + httpx + OpenRouter. Writes a review candidate; --commit overwrites the
trusted corpus."""

from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path

from app.config import BACKEND_ROOT
from app.ingest.pipeline import ingest_client


def _build_adapters(args):
    cass = Path(args.cassettes)
    if args.refresh_fixtures:
        from app.ingest.discover import RecordingDiscoverer, SearxngDiscoverer
        from app.ingest.extract.llm_port import (
            OpenRouterLlmExtractor,
            RecordingLlmExtractor,
        )
        from app.ingest.fetch import HttpxFetcher, RecordingFetcher

        verify = os.getenv("INGEST_TLS_VERIFY", "1") != "0"
        fetcher = HttpxFetcher(verify=verify)
        return (
            RecordingFetcher(fetcher, cass),
            RecordingDiscoverer(SearxngDiscoverer(args.searxng_url, fetcher), cass),
            RecordingLlmExtractor(OpenRouterLlmExtractor(), cass),
        )
    from app.ingest.discover import ReplayDiscoverer
    from app.ingest.extract.llm_port import ReplayLlmExtractor
    from app.ingest.fetch import ReplayFetcher

    return ReplayFetcher(cass), ReplayDiscoverer(cass), ReplayLlmExtractor(cass)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.ingest")
    p.add_argument("client_id")
    p.add_argument(
        "--commit", action="store_true", help="overwrite the trusted snapshot"
    )
    p.add_argument(
        "--refresh-fixtures", action="store_true", help="record live from sources"
    )
    p.add_argument(
        "--cassettes", default=str(BACKEND_ROOT / "tests" / "fixtures" / "ingest")
    )
    p.add_argument("--out-dir", default=str(BACKEND_ROOT / "data"))
    p.add_argument("--synthetic-dir", default=str(BACKEND_ROOT / "data" / "synthetic"))
    p.add_argument(
        "--searxng-url", default=os.getenv("SEARXNG_URL", "http://localhost:8080")
    )
    args = p.parse_args(argv)

    fetcher, discoverer, llm = _build_adapters(args)
    snap = ingest_client(
        args.client_id,
        fetcher,
        discoverer,
        llm,
        captured_at=datetime.date.today(),
        synthetic_dir=Path(args.synthetic_dir),
    )

    out = Path(args.out_dir)
    target = (
        out / "snapshots" if args.commit else out / "candidates"
    ) / f"{args.client_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(snap.model_dump_json(indent=2), encoding="utf-8")

    public_facts = 1 + len(snap.seats) + len(snap.actions)
    where = "COMMITTED to" if args.commit else "candidate written to"
    print(
        f"[{args.client_id}] {where} {target}\n"
        f"  institution funded_ratio={snap.institution.funded_ratio} "
        f"seats={len(snap.seats)} actions={len(snap.actions)} "
        f"(public facts cited: {public_facts})"
    )
    return 0
