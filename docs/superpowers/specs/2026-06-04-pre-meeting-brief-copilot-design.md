# Pre-Meeting Brief Copilot — Backend Design Spec

- **Date:** 2026-06-04
- **Status:** Draft for review
- **Scope owner (this repo):** backend (data, generation, accuracy guard, JSON API)
- **Out of this repo's scope:** the UI (built separately by teammates; a Teams-like chat interface)

---

## 1. Context & problem

Capital Group **institutional relationship managers** (RMs) walk into client meetings — public pensions, corporate DB/DC plans, endowments, insurance general accounts, sovereign funds — without full context. This tool is a **pre-meeting brief "copilot"**: given a client account, it produces a one-page brief (relationship snapshot, risk flags, talking points) before the meeting, and per-participant context during the meeting.

This is a hackathon POC. All data is **mock/synthetic** (`Capital_Group_CRM_mock.xlsx`). "High accuracy & factual" therefore means a hard rule: **every statement in any output must trace back to a fact in the grounding store.** The model never introduces facts; it reasons over and rephrases facts that are already there, and a guard rejects anything unsupported.

The UI is built by teammates as a simulated **Microsoft-Teams-like chat** (React + Vite, in `UI/`): a live **"Sage Agent"** 1:1 chat (calls `POST /api/chat`) plus a static war-room group thread. This repo serves that chat agent **and** structured JSON endpoints. The agent + its grounded tools are the primary integration seam today; the structured endpoints back both the tools and future UI panels.

## 2. Goals / non-goals

**Goals**
- Generate a factual, well-structured **account brief** before a meeting.
- Generate a factual **participant card** on demand (clicking a participant in the chat UI).
- Incorporate **synthetic prior-meeting history** (summaries, decisions, participant interests) into both.
- Guarantee factual accuracy via deterministic risk math + a fact-check guard.
- Be demo-stable: deterministic, fast (cached/pre-warmable), and resilient to a weak/free LLM.

**Non-goals (POC)**
- Building the UI. Real CRM/custodian integration. Authentication/authorization. Real market/performance data. Production TLS. Persistent database. Live meeting transcription.

## 3. Users & demo scenarios

- **User:** an institutional RM (e.g., Diane Okafor, Owen Fitzgerald).
- **Demo accounts** (both code paths exercised; generation is data-driven so any account works):
  - **ACC-1002 — State of Calderon Teachers' Retirement Fund** ("win the mandate"): Prospect, $0 current AUM, Strategic tier, consultant Mercer; two late-stage fixed-income mandates in pipeline (~$346mm Finals Presentation @60%, ~$600mm Due Diligence @80%); contacts span Influencer + two Gatekeepers with **no mapped Decision Maker**.
  - **ACC-1017 — Stonebridge Health System Operating Fund** ("save the relationship"): Healthcare System, ~$2,393mm AUM, **At Risk**, consultant Aon.
- **Two capabilities:** (A) pre-meeting account brief; (B) per-participant card on click.

## 4. Grounding layer (source of truth)

Load `Capital_Group_CRM_mock.xlsx` at startup into typed, in-memory repositories keyed by `Account ID`, behind a `Repository` interface (so a real CRM can swap in later). Sheets and key fields:

- **Accounts** (25): `Account ID`, name, `Type`, `Region`, `AUM with CG ($mm)`, `Tier` (Strategic/Core/Developing), `Client Since`, `Primary Strategy`, `Relationship Mgr`, `Consultant` (In-house, Mercer, Aon, NEPC, RVK, WTW, Callan, Verus), `Status` (Active/Prospect/At Risk). *(The sheet has a trailing totals row; ignore it on load.)*
- **Contacts** (50): `Contact ID`, `Account ID`, name, `Title`, `Role` (Decision Maker / Gatekeeper / Influencer), `Email`, `Phone`, `Last Contacted`.
- **Pipeline** (29): `Opportunity ID`, `Account Name`, `Strategy`, `Mandate Size ($mm)`, `Stage` (Prospecting → Qualification → RFP Submitted → Finals Presentation → Due Diligence → Won/Lost), `Probability`, `Expected Close`, `Owner`.
- **Activities** (69): `Activity ID`, `Date`, `Account Name`, `Contact`, `Type` (Meeting, Call, Email, Conference, Portfolio Review, Webinar), `Subject`, `Owner`, `Next Step`.
- **AUM Summary**, **Team & Org Chart**: roll-ups + internal CG hierarchy (used for peer context / org lookups).

Joins: everything links on `Account ID` / `Account Name`. **"Now" reference date = 2026-06-04** (configurable) for all recency math.

> Reading `.xlsx` requires `openpyxl` (with `pandas`) — to be added to dependencies.

## 5. Synthetic meeting-history generation (offline, frozen)

**Decision: generate offline with a local LLM (Ollama), validate to schema, and commit the output as fixtures.** Runtime only loads fixtures — deterministic, reviewable, fast, and consistent with the CRM because each record is **seeded from a real `Activities` row** (date, subject, participants, next step). Once frozen, these fixtures are treated as ground-truth facts for the demo and are subject to the same guard as CRM facts.

- **Generator:** `scripts/generate_meetings.py`. For each account, take its past meeting-like activities, build prompts, call the **local Ollama** LLM, validate each result against the `MeetingRecord` schema, and write `data/generated/meetings/{ACCOUNT_ID}.json`. Idempotent; can target specific accounts. Output is committed to git.
- **Model:** local Ollama at `http://localhost:11434`. Default `qwen2.5:7b-instruct` if pulled; fallback to the already-present `qwen2.5-coder:7b` (output is schema-constrained, so coder models are acceptable). CPU-only is fine for an offline batch.
- **Consistency rules:** participants must be real `Contact ID`s of that account; decisions/mandates must reference real `Opportunity ID`s/strategies; dates must precede 2026-06-04.

**MeetingRecord schema** (per account file: `{ "account_id": ..., "meetings": [ MeetingRecord ] }`):
```jsonc
{
  "id": "MTG-1002-01",
  "date": "2026-05-07",
  "type": "Call",
  "title": "Performance check-in call",          // seeded from the source Activity
  "participants": ["CON-2004", "CON-2005"],       // real Contact IDs
  "summary": "Concise AI-style executive summary.",
  "decisions": [ { "text": "...", "by": "CON-2004" } ],
  "action_items": [ { "text": "...", "owner": "Diane Okafor", "status": "open" } ],
  "participant_interests": { "CON-2004": ["fee transparency", "downside protection"] },
  "transcript_excerpt": [ { "speaker": "J. Sato", "text": "..." } ],  // short; UI display only
  "source_activity": "ACT-4004",
  "synthetic": true
}
```
**Grounding vs. display:** the runtime LLM grounds and cites the *structured* fields (`summary`, `decisions`, `action_items`, `participant_interests`). `transcript_excerpt` is short and exists for UI realism ("based on the transcript…"); it is not used as a citation source.

## 6. Risk engine (math → deterministic scores)

Pure-Python, deterministic, computed over **all** accounts for peer context. Each component yields a normalized **score in [0,1]** plus an **evidence string** carrying the raw numbers and the fact IDs it derives from.

| Component | Computation |
|---|---|
| Stakeholder coverage | role mix of the account's contacts; high score if **no Decision Maker** mapped |
| Relationship recency | days since most-recent `Last Contacted` vs. peers; older → higher |
| Account status | At Risk → high; Prospect → medium (conversion); Active → low |
| AUM vs. peers | percentile of `AUM` within same `Tier`/`Type`; low percentile or $0-with-pipeline → higher |
| Pipeline dynamics | probability-weighted value, strategy concentration, **days to nearest `Expected Close`** (< 60d → time-sensitive) |
| Loss history | `Lost` opportunities in trailing 12 months (count/value) |
| Consultant influence | `Consultant != In-house` → external-influence factor |
| Open action items | count/age of unresolved `action_items` from meeting fixtures |

**Overall risk** = configurable weighted sum of components, mapped to **severity bands**: `high ≥ 0.66`, `medium 0.33–0.66`, `low < 0.33`. The engine returns the overall score plus a ranked list of components; the top-N feed the brief's risk flags.

## 7. Generation pipeline (math → LLM reasoning → guard → cache)

For both capabilities:
1. **Assemble facts:** repositories + risk engine + meeting fixtures produce a structured, fact-ID-tagged context object (no prose).
2. **LLM reasoning + phrasing:** the LLM receives that context and must return **structured JSON** — it reasons about which items matter most for *this* meeting and writes concise natural language, **citing fact IDs** for each statement. It is instructed it may not introduce numbers/claims absent from the context.
3. **Fact-check guard** (`generation/guard.py`): validates the JSON against the schema; verifies each cited fact ID exists; verifies any number in the text matches a value in the context; **drops** statements that fail. If the LLM/API fails or returns nothing usable, a **deterministic template fallback** produces talking points/explanations from the structured facts so the output never breaks.
4. **Cache:** results cached in-memory by id. Optional **startup pre-warm** generates all briefs so the live demo serves from cache instantly.

**LLM access — two fixed, purpose-specific clients (no runtime switch).** `llm/` exposes two clients sharing a `generate_json(prompt, schema) -> dict` interface. They never cross over: the runtime API never calls Ollama; the offline generator never calls OpenRouter.
- **Runtime "main agent" → OpenRouter only.** `OpenRouterClient` wraps `CertificateBypassingChatOpenRouter` (lifted from `OpenRouter_Agent/agent.py`; `httpx` with `verify=False` to pass the corporate TLS proxy), `OPENROUTER_MODEL` (default `poolside/laguna-m.1:free`, swap to a stronger model before the demo). Used by the brief + participant generation pipeline.
- **Offline transcript/meeting generation → Ollama only.** `OllamaClient` uses `langchain-ollama` `ChatOllama` against `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_MODEL`. Used only by `scripts/generate_meetings.py`.

> `verify=False` is a POC-only workaround (MITM-exposed). Flag for replacement with the corporate CA bundle (`SSL_CERT_FILE`/`verify=<path>`) before any real use.

## 8. API contract (FastAPI under `/api`, JSON — the integration seam)

The UI (Vite, **port 3000**) proxies `/api/*` → `:8000`, so the browser talks only to Vite and **CORS is a non-issue in dev** (we still enable permissive CORS for direct calls). **All endpoints live under `/api`** so the proxy reaches them. Every fact carries a `sources` array of fact IDs for traceability.

**Primary (live) endpoint — what the UI's Sage-Agent chat already calls:**
- `POST /api/chat` — body `{ "message": str, "thread_id": str }` → `{ "reply": str }`; errors → `{ "detail": str }` with a non-2xx status. Served by the OpenRouter ReAct agent (§8a).

**Structured endpoints — also power the agent's tools; for dedicated UI panels later:**
- `GET /api/health` → `{ "status": "ok" }`
- `GET /api/accounts` → **Today's Meetings** list: account summary + derived meeting (`purpose`, `date`, `participant_count`) + `overall_risk` severity, sorted by priority (risk + pipeline urgency).
- `GET /api/accounts/{id}/brief` → **AccountBrief** (below).
- `GET /api/accounts/{id}/participants` → list of `{ contact_id, name, title, role }`.
- `GET /api/participants/{contactId}/brief?accountId={id}` → **ParticipantCard** (below).
- `GET /api/accounts/{id}/meetings` → list of meeting summaries (`id`, `date`, `type`, `title`, `summary`).
- `GET /api/meetings/{meetingId}` → full `MeetingRecord` (incl. `transcript_excerpt`).

### 8a. Runtime main agent (OpenRouter) + grounded tools
`POST /api/chat` is a LangChain ReAct agent (`create_agent`, per `OpenRouter_Agent/agent.py`) using the TLS-bypass OpenRouter chat model with per-`thread_id` memory (`InMemorySaver`). Its tools wrap the **same** engine builders as the REST endpoints, so the chat is grounded:
- `get_account_brief(account_id)` · `get_participant_card(contact_id, account_id)` · `list_today_meetings()` · `get_meeting_history(account_id)` · `lookup_account(query)` · `lookup_contact(query)`.
The fact-check guard runs inside the tools, so any number the agent speaks is grounded. The system prompt requires it to use tools for any account/person/meeting question and never invent facts. Tools return chat-ready markdown; REST returns JSON — both from the same builders.

**AccountBrief**
```jsonc
{
  "account": { "id":"ACC-1002","name":"State of Calderon Teachers' Retirement Fund","type":"Public Pension (DB)",
               "tier":"Strategic","status":"Prospect","aum_with_cg_mm":0.0,
               "primary_strategy":"Capital Group Core Plus Income","relationship_manager":"Diane Okafor",
               "consultant":"Mercer" },
  "meeting": { "purpose":"Advance Bond Fund of America due diligence","date":"2026-06-05","participant_count":3 },
  "headline": "Two late-stage mandates (~$946mm) in play; no decision-maker mapped.",     // LLM, guarded
  "risk_flags": [
    { "id":"coverage","title":"No decision-maker contact mapped","severity":"high","score":0.82,
      "evidence":"3 contacts: 1 Influencer, 2 Gatekeepers, 0 Decision Makers",
      "explanation":"…why it matters for this meeting…",                                    // LLM, guarded
      "sources":["CON-2004","CON-2005","CON-2006"] }
  ],
  "talking_points": [ { "text":"…","sources":["OPP-3003","ACT-4004","MTG-1002-01"] } ],     // LLM, guarded
  "since_last_meeting": { "summary":"…","open_action_items":[ {"text":"…","sources":["MTG-1002-01"]} ] },
  "suggested_next_steps": [ "…" ],
  "meta": { "generated_at":"…","provider":"openrouter","model":"…","grounded_in":["Capital_Group_CRM_mock.xlsx","meeting-fixtures"] }
}
```

**ParticipantCard**
```jsonc
{
  "contact": { "id":"CON-2005","name":"Lisa Schmidt","title":"Plan Administrator","role":"Gatekeeper",
               "account_id":"ACC-1002","last_contacted":"2026-05-16","email":"…","phone":"…" },
  "relationship": { "days_since_contact":19,
                    "recent_interactions":[ {"id":"ACT-…","date":"…","subject":"…"} ] },
  "interests": ["funding/onboarding readiness","operational due diligence"],                // from fixtures
  "prior_decisions": [ { "text":"…","meeting":"MTG-1002-01" } ],
  "meeting_relevance": "Controls committee access; focus on funding/onboarding readiness.", // LLM, guarded
  "talking_point": "Confirm the funding timeline for the $600mm DD mandate.",               // LLM, guarded
  "sources": ["CON-2005","OPP-3003","MTG-1002-01"]
}
```

## 9. Architecture & module layout (repo reorg)

```
backend/
  app/
    config.py            # env + paths (CRM_XLSX_PATH, LLM_PROVIDER, model/base-url vars, weights, NOW date)
    main.py              # FastAPI app, CORS, route wiring, optional startup pre-warm
    data/
      loader.py          # xlsx -> records
      repository.py      # Repository interface + InMemory impl (accounts/contacts/pipeline/activities/meetings)
    domain/models.py     # pydantic models (entities + RiskFlag, TalkingPoint, AccountBrief, ParticipantCard, MeetingRecord)
    risk/
      engine.py          # components -> scores + evidence -> overall + severity
      peers.py           # percentile / peer-median calcs
    generation/
      brief.py           # account brief assembly + LLM + guard
      participant.py     # participant card assembly + LLM + guard
      guard.py           # fact-check guard + template fallback
      prompts.py         # prompt templates
    llm/
      base.py            # shared generate_json(prompt, schema) interface
      openrouter_client.py  # OpenRouterClient — runtime only (CertificateBypassingChatOpenRouter, lifted from OpenRouter_Agent)
      ollama_client.py      # OllamaClient — offline generator only
    api/
      routes.py          # REST endpoints (under /api): accounts, brief, participants, meetings
      chat.py            # POST /api/chat -> agent
    agent/
      tools.py           # @tool wrappers over the engine (brief, participant, meetings, lookups)
      runtime.py         # build the OpenRouter ReAct agent (create_agent + tools + InMemorySaver)
  scripts/generate_meetings.py   # offline synthetic meeting generator (Ollama only)
  data/generated/meetings/       # committed fixtures
  data/source/Capital_Group_CRM_mock.xlsx   # (or reference repo-root copy via CRM_XLSX_PATH)
  preview.html                   # tiny self-test viewer to see briefs without the real UI
  requirements.txt
```
`OpenRouter_Agent/` is kept as reference; its TLS-bypass client is lifted into `backend/app/llm/openrouter_client.py`.

## 10. Tech stack & dependencies

- **Python 3.12**, **FastAPI** + **uvicorn[standard]**, **pydantic v2**.
- **pandas** + **openpyxl** (xlsx), **python-dotenv**.
- **langchain**, **langchain-openrouter** (runtime), **langchain-ollama** (offline/local), **httpx**.
- Front-end (teammates): React + Vite + TypeScript + Tailwind; dev server proxies `/api/*` to `:8000`.

## 11. Configuration (env)

`OPENROUTER_API_KEY` · `OPENROUTER_MODEL` (runtime main agent) · `OLLAMA_BASE_URL` · `OLLAMA_MODEL` (offline generator) · `CRM_XLSX_PATH` · `NOW_DATE` (default `2026-06-04`) · `PREWARM` (bool) · risk weights. There is **no** runtime provider switch — runtime is always OpenRouter, generation is always Ollama. `.env` is gitignored.

## 12. Demo flow

1. Pre-generate meeting fixtures offline (local Ollama) and commit them.
2. Start backend with `PREWARM=1` (all briefs cached at startup).
3. Run `UI/` (`npm run dev`, port 3000) + backend (port 8000). In the **Sage Agent** chat: *"Brief me for the Calderon Teachers' meeting"* → grounded brief; *"What should I know about Liam Mitchell?"* → participant card; the **War Room** thread gives ambient context. (When REST panels are built, the same data renders as a Today's Meetings list + brief card.)

## 13. Risks & mitigations

- **Weak/free runtime model quality** → math owns all numbers/flags; LLM only phrases; guard + template fallback; swap to a stronger OpenRouter model and pre-warm before the demo.
- **CPU-only latency** → all heavy generation is offline or pre-warmed; live demo serves cache.
- **Corporate TLS** → `verify=False` POC workaround for OpenRouter; local Ollama avoids the network entirely.
- **Synthetic data mistaken for real** → every payload is explicitly grounded in the mock dataset; records flagged `synthetic: true`.
- **Live API key in `.env`** → gitignored; rotate if the source repo was ever pushed/public.

## 14. Parallel development tracks

Time-constrained, so after a small shared foundation the work splits into two **independent** tracks built concurrently. The only cross-track dependency is the `MeetingRecord` schema (fixed in Phase 0) and the fixtures (Track B → Track A), bridged by a Phase 0 sample fixture so neither track blocks the other.

**Phase 0 — shared foundation (do first; small, unblocks both):**
- Project scaffold + dependencies (§10) + `config.py`.
- `domain/models.py` — all pydantic models, including `MeetingRecord` (the contract both tracks agree on).
- `data/loader.py` + `data/repository.py` — load the xlsx into repositories.
- One hand-authored **sample** fixture (`data/generated/meetings/ACC-1002.json`) so Track A can integrate before Track B finishes.

**Track A — runtime "main agent" (OpenRouter only):**
1. `llm/openrouter_client.py` (TLS-bypass chat model + `generate_json` client).
2. `risk/engine.py` + `risk/peers.py` — deterministic, unit-testable, no LLM.
3. `generation/brief.py`, `generation/participant.py`, `generation/guard.py`, `generation/prompts.py` (+ template fallback).
4. `agent/tools.py` + `agent/runtime.py` — wrap the engine builders as ReAct-agent tools.
5. `api/routes.py` (REST) + `api/chat.py` (`POST /api/chat`) + `app/main.py` (FastAPI mounted under `/api`, permissive CORS, cache, optional pre-warm) + `preview.html`.
- Develops against the Phase 0 sample fixture; reads real fixtures once Track B lands. Makes the existing `UI/` Sage-Agent chat work end-to-end.

**Track B — offline transcript/meeting generation (Ollama only):**
1. `llm/ollama_client.py`.
2. `scripts/generate_meetings.py` + generation prompts + `MeetingRecord` schema validation.
3. Generate, review, and **commit** fixtures for all accounts (rich for ACC-1002 and ACC-1017).

**Integration (short):**
- Track A consumes Track B's committed fixtures; validate both demo accounts end-to-end through the API + `preview.html`.

## 15. Open setup item

- Pull `qwen2.5:7b-instruct` for nicer offline prose, or proceed with the already-present `qwen2.5-coder:7b`. Default: use `qwen2.5:7b-instruct` if available, else fall back to `qwen2.5-coder:7b`.
