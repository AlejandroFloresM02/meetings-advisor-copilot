# V2 — A2: Public-Layer Ingestion Pipeline — Design Spec

> Sub-project **A2** of the V2 data foundation. Builds the offline ingestion pipeline (parent spec §4, §7, §11) that constructs the committed snapshot corpus. Parent spec: `docs/superpowers/specs/2026-06-04-v2-grounded-brief-data-foundation-design.md`. Builds on **A1** (deterministic data core — done): `docs/superpowers/plans/2026-06-04-v2-grounded-brief-data-foundation.md`.

## 1. Context & locked decisions

A1 delivered the typed, provenance-tagged data core (models, snapshot, repository, derived layer, guard, brief assembler) over a **hand-authored** CalPERS snapshot. A2 replaces the hand-authoring of the *public* layer with a real, offline-testable ingestion pipeline that discovers, fetches, extracts, validates, and commits public facts — turning retrieval into **corpus construction**, not live scraping (parent §4).

Decisions locked in brainstorming (2026-06-06):

1. **Full live pipeline with SearXNG** — real `discover → fetch → extract → assemble → validate → commit`.
2. **Hybrid extraction** — deterministic parsers for structured sources; LLM (via `app/llm`) for unstructured prose.
3. **Record & replay fixtures** — network + LLM behind ports; cassettes committed; the test suite stays offline and deterministic (green like A1).
4. **CalPERS end-to-end** — prove every stage on one client; adding the other demo clients (parent §3) becomes repeatable data work, not new architecture.
5. **Public layer only (Approach A)** — ingest the real public layer; keep the synthetic CG layer + personas hand-authored and merge them at assemble time. CG-published ingestion (B) and synthetic regen + §6 E/F entities (C) are deferred.

## 2. Goals / non-goals

**Goals**
- A real `discover → fetch → extract → assemble → validate → commit` pipeline producing the **public layer** of a client snapshot.
- Proven end-to-end on **CalPERS**, producing the same `backend/data/snapshots/CALPERS.json` the A1 runtime already reads.
- Network + LLM behind narrow ports with **record/replay** fixtures → deterministic, offline test suite.
- **Provenance** (`public` + `url` + `fetched_at`) on every fetched fact; assemble rejects an un-sourced public fact.
- **Idempotent**, per-client, CLI-targetable; never writes a worse snapshot than the last committed one.

**Non-goals (A2 first pass)**
- CG fact-sheet / house-view ingestion → `StrategyProfile`/`HouseView` (Approach B — fast-follow once ingestibility is confirmed, parent §13).
- LLM-generated synthetic layer regen + ODD / PM-firm-governance entities (§6 E/F) (Approach C — later increment).
- The other demo clients — CalSTRS, UTIMCO, Texas TRS, Florida SBA (repeatable data work after the pipeline lands).
- Live runtime refresh of the `live` slice (sub-project B).
- SearXNG infrastructure automation beyond a documented compose + settings file.
- **No taxonomy expansion** — A1's `Institution` / `GovernanceSeat` / `InvestmentAction` already cover the public layer (small optional fields only if a source demands one).

## 3. Architecture & principles

Ports-and-adapters, carrying A1's discipline:

- **Side effects at the edges.** Network (`fetch`, `discover`) and the LLM live behind narrow interfaces; `extract` and `assemble` are pure functions over their inputs.
- **Record/replay.** Each port has a `Recording*` adapter (writes a cassette from a live call) and a `Replay*` adapter (serves the committed cassette). Tests use replay → no network/LLM, fully deterministic.
- **Isolated extractors.** One extractor per source type: input `FetchedDoc`, output typed, provenance-tagged model fragments. Each is understood and tested without the others.
- **Provenance at fetch time.** `url` + `fetched_at` are stamped when a document is fetched and ride through extraction into each fact's `Provenance`.
- **Idempotent.** A fetch/extract/validate failure logs and keeps the prior committed snapshot; the pipeline never commits a regression.
- **Output conforms to A1.** The assembled object is an A1 `Snapshot`; `build_brief` must still succeed on it.

```
[ source registry ] ─discover(SearXNG)|known-URL→ [ fetch (httpx) ] ─→ [ hybrid extract per source ]
                                                                              │ public fragments (url + fetched_at)
                                                                              ▼
[ authored synthetic layer ] ───────────────────────────────────────▶ [ assemble + validate ]
                                                                              │ candidate Snapshot
                                                                              ▼
                                                       [ review (CLI summary) ] ─--commit→ [ data/snapshots/CALPERS.json ]
                                                                                                    │
                                                                                                    ▼  (A1 runtime reads it)
```

## 4. Components (units) — `backend/app/ingest/`

| Unit | Does | Interface | Depends on |
|---|---|---|---|
| `sources.py` | The allowlist as data: per-client source descriptors (URL/domain → extractor → fact-types). | `sources_for(client_id) -> list[SourceDescriptor]` | — |
| `models.py` | Ingestion value objects. | `FetchedDoc`, `SourceDescriptor`, `IngestResult` | pydantic |
| `discover.py` | SearXNG client port, allowlist-constrained; bypassable when the descriptor carries a canonical URL. | `Discoverer.discover(query, allowed_domains) -> list[SearchResult]` | httpx |
| `fetch.py` | Fetcher port; HTML + PDF bytes; `verify` overridable via env. | `Fetcher.fetch(url) -> FetchedDoc` | httpx |
| `extract/publicplans.py` | Deterministic parse of Public Plans DB data. | `extract(doc) -> InstitutionFacts` | — |
| `extract/acfr.py` | ACFR PDF text + LLM extraction of high-signal facts. | `extract(doc, llm) -> InstitutionFacts` | pypdf, llm_port |
| `extract/board.py` | Board/staff HTML + LLM for committee priorities. | `extract(doc, llm) -> list[GovernanceSeat]` | selectolax, llm_port |
| `extract/news.py` | P&I / press HTML + LLM. | `extract(doc, llm) -> list[InvestmentAction]` | selectolax, llm_port |
| `extract/llm_port.py` | Narrow LLM port for structured extraction; record/replay-able. | `LlmExtractor.extract(prompt, schema) -> dict` | `app/llm` |
| `assemble.py` | Merge public fragments + authored synthetic layer → `Snapshot`; validate; assert provenance. | `assemble(public, synthetic) -> Snapshot` | A1 models |
| `pipeline.py` | Orchestrator. | `ingest_client(client_id, fetcher, discoverer, llm) -> Snapshot` | the above |
| `cli.py` | `python -m app.ingest CALPERS [--commit] [--refresh-fixtures]`; writes candidate + review summary. | `__main__` | pipeline |

Record/replay adapters (`ReplayFetcher`/`RecordingFetcher`, and the same for discover + LLM) live beside their ports, keyed by URL / query / prompt-hash. Cassettes are committed under `backend/tests/fixtures/ingest/`.

## 5. Source registry & allowlist (CalPERS first pass)

| Fact group | Source(s) | Extractor | Method | Provenance |
|---|---|---|---|---|
| Funded ratio, plan assets, allocation | Public Plans Database | `publicplans` | deterministic | `public` (+url, fetched_at) |
| Funded ratio, assumed return, allocation, fiscal year (cross-check) | CalPERS ACFR/CAFR (PDF) | `acfr` | PDF text + LLM | `public` |
| Governance seats: title, remit, decides, committee, priorities | CalPERS board & staff pages, agendas/minutes | `board` | HTML + LLM | `public` |
| Investment actions: hires/terminations/searches/watch | *Pensions & Investments*, CalPERS press page | `news` | HTML + LLM | `public` |

Everything off the allowlist is ignored (parent §4). `discover` (SearXNG) finds the live URLs within these domains; where a canonical URL/endpoint is known (e.g. the Public Plans DB), the descriptor carries it and `discover` is bypassed.

## 6. Extraction strategy (hybrid)

- **Deterministic** for structured data (Public Plans DB rows/JSON, HTML tables): direct parse, no LLM — fully reproducible.
- **LLM** for unstructured prose (ACFR narrative/tables, board minutes, news): the `llm_port` asks for **structured output** matching a small extraction schema, returning typed fragments. Numbers it emits still face A1's groundedness guard downstream; the deterministic Public Plans DB values cross-check the ACFR-extracted figures where they overlap.
- The LLM uses the existing `app/llm` OpenRouter client (its `CertificateBypassing` variant already handles the corporate TLS proxy). The `llm_port` is record/replay-able (cassette keyed by prompt hash), so extraction is deterministic in tests.

## 7. Provenance, validation & the synthetic split

- Every public fragment carries `Provenance(kind="public", url=<source>, fetched_at=<date>)`, stamped at fetch.
- `assemble` validates the merged object against the A1 `Snapshot` model and asserts that **every public-layer fact carries `url` + `fetched_at`**; a public fact missing provenance fails the build.
- **Public vs synthetic split.** A1's `CALPERS.json` currently holds both layers. A2 separates them:
  - **Ingested (public):** `institution`, `seats`, `actions`.
  - **Authored (synthetic), in `backend/data/synthetic/CALPERS.json`:** `people` (personas), `mandates`, `pipeline`, `relationship`, `interactions`, `meetings`.
  - `assemble` combines them — the ingested public layer sets `client_id` and `captured_at` (the ingestion date), the synthetic file contributes its entity lists — into the committed `backend/data/snapshots/CALPERS.json`, which therefore becomes a **build output** of A2 (still committed; A1's tests still read it unchanged).
- **Human review (parent §4 steps 3–4):** `cli` writes the candidate snapshot plus a summary (field counts, sources cited, diff vs the committed snapshot) for review; `--commit` overwrites the corpus only on demand.

## 8. Error handling & fallback

- **Fetch / discover / LLM failure or timeout** → log and keep the prior committed snapshot (idempotent; never write a regression).
- **SearXNG down** → fall back to the descriptor's canonical URLs; `discover` is an optimization, not a hard dependency.
- **Extraction empty or invalid** → drop that fragment, keep the prior value; A1's guard guarantees an un-sourced fact never reaches a brief.

## 9. Testing (record/replay)

- **Per-extractor unit tests**: feed a recorded `FetchedDoc` fixture → assert the typed output and its provenance. Deterministic, offline.
- **Pipeline test**: replay the fetch/discover/LLM cassettes end-to-end → assert the produced CalPERS snapshot shape, that every public fact is provenance-complete, and that A1's `build_brief` still succeeds on the result.
- Cassettes committed under `backend/tests/fixtures/ingest/`; `--refresh-fixtures` re-records from live (requires SearXNG + network + an LLM key).
- pytest + strict-ruff discipline carried from A1; the suite remains green and offline in CI.

## 10. Dependencies, file layout & SearXNG ops

**New deps** (`backend/requirements.txt`): `httpx` (fetch), `pypdf` (ACFR text), `selectolax` (HTML). LLM via the existing `app/llm`.

```
backend/
  app/ingest/
    __init__.py  sources.py  models.py  discover.py  fetch.py
    assemble.py  pipeline.py  cli.py
    extract/__init__.py  llm_port.py  publicplans.py  acfr.py  board.py  news.py
  data/
    synthetic/CALPERS.json     # authored CG layer (people/mandates/pipeline/relationship/interactions/meetings)
    snapshots/CALPERS.json     # build output of assemble (public + synthetic)
  tests/
    fixtures/ingest/...        # committed cassettes (fetched bodies, discover JSON, LLM responses)
    test_ingest_*.py
infra/searxng/
  docker-compose.yml  settings.yml   # JSON format + allowlist enabled
```

**SearXNG operationalization.** `infra/searxng/` carries a `docker-compose.yml` + `settings.yml` (JSON output format and the trusted-domain allowlist enabled). The pipeline reads `SEARXNG_URL` (default `http://localhost:8080`). The user runs `docker compose up -d` once to record fixtures; the test suite never touches it. (Docker is installed in the dev env but the daemon must be started.)

## 11. Open questions & risks

- **Source structural drift** — ACFR PDF layouts and board pages change year to year. Mitigation: fixtures pin a known vintage; `--refresh-fixtures` + re-review on drift.
- **LLM extraction accuracy** on PDFs/prose. Mitigation: extract only high-signal fields; cross-check ACFR figures against the deterministic Public Plans DB values; the guard drops unsupported numbers.
- **Corporate TLS at the user's run-env** — `fetch` exposes a `verify` override (env-driven, defaults on since the probe shows TLS works here); `app/llm` already bypasses for OpenRouter.
- **Source availability / ToS** — only allowlisted public sources; corpus is curated and committed, not live-scraped at request time; respect robots/ToS on fetch (parent §8).
- **SearXNG value on one client** — for CalPERS most sources have canonical URLs, so `discover` mainly proves the spec's discover step; its payoff grows as more clients are added.

## 12. What A2 delivers

A real, offline-tested **public-layer ingestion pipeline** that builds CalPERS's committed snapshot from cited public sources, with the architecture making additional clients and source types incremental — the corpus-construction engine behind the parent spec's §4, with A1's grounding discipline intact.
