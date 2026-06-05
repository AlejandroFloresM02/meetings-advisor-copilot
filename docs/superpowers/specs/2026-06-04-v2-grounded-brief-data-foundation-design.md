# V2 — Grounded Brief: Data & Grounding Foundation — Design Spec

- **Date:** 2026-06-04
- **Status:** Draft for review
- **Supersedes:** `2026-06-04-pre-meeting-brief-copilot-design.md` (V1). V1's closed mock-CRM grounding and disjoint UI/agent model are intentionally replaced; V1's *engine patterns* (deterministic math → LLM phrasing → fact-check guard → cache) are kept.
- **Scope (this spec):** sub-project **A — the data model, grounding sources, ingestion pipeline, provenance/guardrails, the brief content contract that the data must satisfy, and the evaluation framework.**
- **Deferred to later specs:** **B** backend service + agent runtime/routing; **C** JSON API contract; **D** the dashboard UI. This spec defines *what data exists, where it comes from, how it's trusted, and what output it must support* — not how the service or UI are built.

---

## 1. Context & product thesis

Capital Group ($3T+ in AUM) institutional **relationship managers** (RMs) meet clients — US public pensions, endowments, insurance general accounts. This product generates, **before the meeting and in under 60 seconds**, a digestible **insight dashboard** (not a prose paragraph) so the RM walks in materially better prepared than without it.

This is a solo-developer **V2 remake** (branch `v2`). V1's weaknesses being corrected: the brief was weakly grounded; the UI war-room used *internal CG colleagues* disjoint from the CRM's *client contacts*; the "agent" was a single ReAct loop that guessed the account from free text; and the data model was thin. V2's distinctive bet is **real grounding**: the meeting clients are **real public institutions**, their public facts are genuinely sourced and cited, recommendations lean on **Capital Group's real published house views**, and only the confidential CG-relationship layer is synthetic (and clearly labeled).

All numbers and claims in any output must **trace to a provenance-tagged fact** or be dropped — the V1 discipline, hardened.

## 2. Goals / non-goals

**Goals**
- A fresh, well-designed data model whose every field has a known **provenance** (`public` / `cg_house_view` / `synthetic` / `derived`).
- **Real public-institution grounding** via a curated, citable snapshot corpus (see §4), with Capital-Group house views grounding recommendations.
- A **brief content contract** (insight units, scenario-driven anatomy) that the data is proven to satisfy (§9).
- A **financial/technical analytics layer** in correct institutional vocabulary (§6), validated against industry platforms.
- **Provenance + guardrails** that limit (not "eliminate") hallucination, avoid PII, and refuse out-of-scope asks (§8).
- An **offline evaluation framework** (RAG Triad + per-scenario graded set) so quality is measurable, not asserted (§10).
- Sub-60s generation **conditional on pre-warm/cache** (§7).

**Non-goals (this spec / POC)**
- Real CG client data or real client relationships (the CG layer is synthetic). Real-time market/portfolio analytics computed from raw time series. Authentication. Production deployment. The backend service, agent runtime, API contract, and UI (later specs). Profiling of named real individuals (see §8 PII policy).

## 3. Demo client set

Real, genuinely transparent US public asset owners (~5–6; final selection may adjust): **CalPERS, CalSTRS, UTIMCO** (endowment), **Texas TRS, Florida SBA** — a spread of public pensions plus a public university endowment for client-type variety. Each is fully sourced and committed as a snapshot (§4, §11); the data model is client-type-agnostic so others can be added.

## 4. Grounding strategy — a curated snapshot corpus (core of V2)

**The key design decision, refined against the state of the art.** No comparable production system grounds in the open web (Morgan Stanley's assistant uses RAG over a *closed* ~100k-document internal corpus; BlackRock's Aladdin Copilot is scoped to its *own* APIs). Open-web fetch at request time carries scraping-legality, reliability, freshness-consistency, and PII risk. We keep the real-public-data differentiator **and** adopt the SOTA-safe posture by treating retrieval as **corpus construction**, not live scraping:

```
discover → fetch → extract → validate → review → COMMIT (trusted corpus)  ──▶  runtime reads the committed corpus
                                                                              (+ best-effort live refresh of the "live" slice, with snapshot fallback)
```

1. **Discover** — self-hosted **SearXNG (Docker)**, configured to search **only an allowlist of trusted domains** (privacy-respecting, no query leakage, fully controllable).
2. **Fetch & extract** — pull allowlisted pages, extract structured facts, attach **source URL + fetch timestamp** to each.
3. **Validate & review** — schema-validate; the snapshot is human-reviewable before commit.
4. **Commit** — the per-client snapshot is committed to the repo as a **trusted, versioned corpus**. At request time the runtime reads this closed, vetted corpus — matching the SOTA closed-corpus pattern.
5. **Hybrid freshness** — each field is tagged `frozen` or `live`:
   - `frozen` (served from the committed snapshot): institution profile, funded status, asset allocation, governance seats, CG synthetic layer, house views.
   - `live` (best-effort refresh at generation, short-TTL cache, **fallback to snapshot** on timeout/failure): recent news, latest manager moves, upcoming agenda.

**Trusted-domain allowlist (source map).**

| Data | Allowlisted sources |
|---|---|
| Institution profile, funded status, allocation, governance, manager roster, fees-where-disclosed | the fund's own site (ACFR/CAFR, Investment Policy Statement, board packets, allocation/holdings reports); the Public Plans Database |
| Investment actions, manager hires/terminations, searches/RFPs, news | *Pensions & Investments*, *Chief Investment Officer*, the fund's press page |
| Governance seats, committee priorities | the fund's board & staff pages, meeting agendas/minutes |
| CG house views / Capital Market Assumptions; CG strategy fact sheets; CG PM bios | `capitalgroup.com` |
| Benchmarks / market reference | a frozen reference series for the POC |

Everything off the allowlist is ignored. See §13 open item on CG house-view ingestibility/licensing.

## 5. Data model — entity taxonomy

Every field carries a `provenance` tag: `public` (+`url`, `fetched_at`) · `cg_house_view` (+`url`) · `synthetic` · `derived`.

### ① The client institution — *public (+ derived for comparisons)*
`Institution` — id, name, type (public pension / endowment / insurance GA), plan assets, fiscal year, **funded_ratio, assumed/discount rate**, actuarial vs market value, **asset_allocation {class: target%, actual%}**, in-house vs external mix, policy benchmark.

### ② The people in the room — *real seats (public) + imagined personas (synthetic)*
`GovernanceSeat` — title, remit, **what it decides**, committee, **public priorities** (cited from minutes/agendas). *public*
`Person` — **imagined name over the real seat**, plausible-but-fictional background, engagement notes. *synthetic identity occupying a public seat — no real-individual PII (see §8).*

### ③ The CG relationship & portfolio — *synthetic, labeled, seeded from the real client*
`CGMandate` / `CGHolding` — strategy, vehicle, mandate size, fee schedule, inception; performance vs benchmark, flows, attribution. *synthetic, sized realistically against the institution's real allocation.*
`Opportunity` (pipeline) — strategy, size, stage, probability, expected close, owner.
`RelationshipMeta` — RM, tier, consultant (Mercer/Aon/…), status, client-since.
`Interaction` — prior meeting/call, summary, decisions, open action items.

### ④ Market & investment context — *cg_house_view + public + frozen reference*
`HouseView` — CG asset-class outlook + themes (Capital Market Assumptions: expected return/vol/correlation). *cg_house_view.*
`StrategyProfile` — CG strategy technicals (duration, OAS, credit quality, sector mix, active share, returns, expense ratio). *public via CG fact sheets* where the strategy maps to a public CG fund; else synthetic-but-realistic.

### ⑤ The upcoming engagement — *synthetic + derived* **(added by working backward from the output)**
`Meeting` — date, purpose, **objective / "the ask"**, **scenario** ∈ {portfolio review, finals presentation, at-risk save, relationship review}, attending `GovernanceSeat`s, type. The `scenario` drives section prioritization (§9).
`Snapshot` + `Delta` — retained prior snapshots + computed period-over-period changes (powers "what's changed"). *derived.*

### ⑥ Derived layer — *derived (deterministic, no LLM invention)*
`RiskFlag` — funded gap, manager-on-watch, fee pressure, near-term close, coverage gap; score + evidence + sources.
`PeerComparison` / `CostEffectiveness` — peer-/universe-relative metrics **and net-value-added vs excess-cost framing** (§6).
`Recommendation` — strategy-fit tying `HouseView` → the institution's allocation gap.

## 6. Financial & technical analytics layer

Validated against eVestment, CEM, Addepar, MSCI (vocabulary is correctly termed). Organized by the client's area; provenance noted.

- **A · Total-plan (asset-owner)** — *public + derived.* funded ratio, assumed/discount rate, spending rate vs HEPI (endowments); **total-fund return vs policy benchmark**; asset-class returns vs class benchmarks; **SAA target vs actual** + rebalancing bands; tracking-error budget, liquidity profile, **commitment pacing**, vintage diversification.
- **B · Fixed income** — *strategy technicals public via fact sheet; mandate overlay synthetic.* effective & key-rate **duration** vs benchmark, **YTW/YTM**, **OAS / spread duration**, convexity, carry; credit-quality & sector mix; **net-of-fee excess, tracking error, information ratio, down-market capture** vs Bloomberg US Agg; rate-regime positioning.
- **C · Equity** — *same split.* **active share**, factor/style & sector/region tilts, concentration/top-10, valuation vs index; net-of-fee excess vs MSCI ACWI, **information ratio, up/down capture, batting average**.
- **D · Private markets / alts** — *derived/synthetic.* commitment pacing, vintage diversification, **J-curve stage, DPI/TVPI/IRR**, NAV vs commitments, illiquidity budget.
- **E · Due diligence** — *mix.*
  - *Investment DD signals:* strategy **AUM/capacity**, team turnover/key-person, style drift, **fee schedule/breakpoints**, vehicle (SMA/CIT/commingled).
  - *Operational DD core* **(added in V2 scope):* valuation policy, IT/cyber, compliance, internal controls & segregation of duties, trade lifecycle, third-party service-provider verification. (Framed as what an asset owner scrutinizes about a manager.)
- **F · Manager & firm** **(added in V2 scope)** — *public.* **PM/team bios** (CG publishes these), **firm ownership/governance** structure (CG = private partnership; competitors vary).
- **G · Cost-effectiveness** **(added in V2 scope)** — *derived.* reframe raw fees as **net value added (net return − policy return) vs. excess cost vs. size/focus-matched peers** (CEM "Cost Effectiveness Analysis" framing).
- **H · Market & CMAs** — *cg_house_view + frozen reference.* rate path/curve/spreads, equity valuations; CG Capital Market Assumptions powering recommendations.

**Feasibility:** no quant engine required — public funds publish headline returns/allocations (cite them), CG fact sheets publish strategy technicals (cite them), the synthetic mandate carries authored-but-realistic figures, and the derived layer computes only simple things (vs-benchmark deltas, peer percentiles, NVA-vs-cost, risk flags). For the demo we populate the **high-signal metrics per scenario**, not every field.

## 7. Ingestion pipeline & the latency budget

- **Offline ingestion** (per client): the discover→fetch→extract→validate→review→commit pipeline of §4 produces a committed snapshot. Idempotent; targetable per client.
- **Synthetic layer**: a fresh schema (not V1's xlsx), **LLM-generated then frozen & committed**, *seeded from the real snapshot* so it's consistent (a CG fixed-income mandate sized against the fund's real FI allocation; personas in real seats). Schema-validated, reviewable, never invented at runtime.
- **At generation**: read the committed snapshot instantly; pre-render the deterministic (derived) sections; **fan out subagents** for the `live` slice in parallel; assemble insight units.
- **Latency**: the **<60s budget is explicitly conditional on pre-warm/cache** (a hierarchical/selective-verification pipeline supports this; reflexive self-correction loops do not). Cold-path latency is **not** guaranteed and is a tracked risk (§13).

## 8. Provenance & guardrails

- **Provenance on every fact** — `public`(+url, fetched_at) / `cg_house_view`(+url) / `synthetic` / `derived`. Every brief statement cites the provenance of the facts it rests on. (This is *more* rigorous than the published Aladdin approach — a deliberate differentiator.)
- **Fact-check gate, not elimination** — the guard is a hard **groundedness gate**: numbers/claims must trace to a tagged fact or be dropped, with a deterministic **template fallback**. Design language avoids any "zero-hallucination" claim — guardrails *limit* risk.
- **PII / persona policy** — for the POC, **no real individuals are named or profiled**; personas are synthetic, occupying **real public seats**; real data attaches at institution/seat/committee level only. (Independently vindicated: Aladdin blocks PII; Morgan Stanley requires client consent — no comparator profiles named individuals.)
- **Out-of-scope refusal + disclaimer** — the agent **refuses to give investment advice** and refuses off-scope questions, and surfaces an **"AI-generated — always verify"** disclaimer (industry-standard, per Aladdin/MS).
- **Legal/scraping posture** — only allowlisted, public sources; corpus is curated/reviewed, not live-scraped at request time; respect robots/ToS on fetch. The synthetic layer is labeled in every payload.

## 9. Brief content contract (the output the data must satisfy)

**Format principles:** (1) every item is an **insight unit**, never a raw field; (2) **progressive disclosure** (glance → detail → cited evidence); (3) **ranked by urgency**, not by category.

**Insight-unit atom:** `Insight` (synthesized claim) · `Why now` (so-what for this meeting) · `Evidence` (facts + provenance) · `Play` (recommended talking point/action) · `freshness` (frozen/live).

**Brief anatomy (ordered by decision-value; the `Meeting.scenario` decides what surfaces first):**
1. **Bottom line (BLUF)** — the single thing that decides this meeting.
2. **Meeting frame** — purpose, the ask, who's in the room, when. *(needs ⑤ `Meeting`)*
3. **What's changed since last contact** — deltas. *(needs ⑤ `Snapshot`/`Delta`)*
4. **Risks & opportunities** — ranked, relationship-specific, each with a play.
5. **The room** — per seat: power, priorities, how to engage, landmines.
6. **Portfolio position** — CG holdings vs benchmark + the attribution story.
7. **Recommended plays** — house view + strategy-fit → the client's gap → what to say.
8. **Anticipated Q&A** — likely pushback + grounded responses.
9. **Next step / the ask.**

Glance layer = **1, 3, 4, 5**; the rest is drill-down. **Scenario → emphasis:** *win/grow* → strategy-fit (net-of-fee excess, IR, active share/down-capture, capacity, CMAs); *reduce risk* → funded ratio, duration/rate exposure, concentration, liquidity, pacing, TE budget; *defend/divert* → after-fee defense, attribution, fee/vehicle alternative, ODD reassurance.

## 10. Evaluation framework (added in V2 scope)

Runtime guard ≠ quality measurement. Adopt the **RAG Triad**, mapped edge-by-edge to the pipeline, as an **offline** harness:
- **Context relevance** — retrieved/snapshot facts are relevant to the brief's needs (retrieval edge).
- **Groundedness / faithfulness** — every generated claim is supported by a cited fact (generation edge) — the runtime guard is the hard gate for this; offline we also score it.
- **Answer relevance** — the brief actually serves the meeting/scenario (output edge).

Plus a **small, per-scenario, human-graded eval set** (portfolio review / finals / at-risk save / relationship review) with explicit acceptance bars, run as a regression suite — the table-stakes practice Morgan Stanley uses. *Caveat:* LLM-as-judge scoring has known reliability/cost/latency limits; numeric-claim groundedness is enforced deterministically by the guard, not the judge.

## 11. Storage & format

- Per-client **structured JSON snapshots**, committed & versioned (prior snapshots retained for deltas). SQLite optional later.
- One snapshot file per client holds: institution + seats + investment actions (public), the synthetic CG layer, the meeting(s), and the embedded provenance tags. House views and CG strategy profiles are shared/global snapshots.

## 12. Architecture map (what this spec establishes vs defers)

```
[ SearXNG allowlist ] ─discover→ [ fetch/extract ] ─→ [ validate/review ] ─commit→ [ committed snapshots (trusted corpus) ]
                                                                                          │
[ CG fact sheets / CMAs ] ──────────────────────────────────────────────────────────────┤  ← this spec (sub-project A)
[ synthetic CG layer (seeded, frozen) ] ─────────────────────────────────────────────────┤
                                                                                          ▼
                                                              [ derived layer: risk / peer / cost-effectiveness / deltas ]
                                                                                          ▼
                              ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ deferred ─ ─
                              [ generation: assemble → LLM phrasing → guard → cache ]  (sub-project B)
                              [ JSON API contract ]  (sub-project C)   ·   [ dashboard UI ]  (sub-project D)
```

## 13. Open questions & risks

- **CG house views / CMAs**: confirm they exist in a machine-ingestible, license-clear form at a known refresh cadence before relying on them for recommendations; else mark recommendations *illustrative*. *(unverified in research)*
- **Cold-path latency**: the <60s budget holds for pre-warmed/cached paths; cold generation against the runtime model is unproven — measure early.
- **Architecture transfer**: the hierarchical/selective-verification cost-accuracy result comes from one preprint scoped to SEC-filing extraction; treat as a prior, validate on our workload.
- **LLM-as-judge** reliability in the eval harness — keep deterministic gates for anything load-bearing.
- **Scraping/compliance**: even allowlisted public sources warrant a documented robots/ToS posture; the curated-corpus approach is the mitigation.

## 14. Research basis

This spec was pressure-tested against a deep-research scan (FS/wealth copilots, account-intelligence tools, institutional analytics platforms, grounding/speed architecture; 24 sources, 21 verified claims). Key load-bearing sources: Morgan Stanley/OpenAI case study; BlackRock Aladdin Copilot; Gong AI Briefer; Nasdaq eVestment; CEM Benchmarking; SEI operational due diligence; TruLens RAG Triad; *Benchmarking Multi-Agent LLM Architectures for Financial Document Processing* (arXiv 2603.22651, medium confidence).
