# Pre-Meeting Brief Copilot — Presentation Keynotes

## The one-liner
A pre-meeting brief copilot for Capital Group institutional RMs. Give it a client
account and it produces a grounded one-pager — relationship snapshot, ranked risk
flags, talking points — plus an in-meeting agent that answers from CRM, prior
meetings, and the live conversation. **Math computes the risk, the LLM only phrases
it, and a fact-check guard drops anything unsupported.**

## How the risk score is calculated (the differentiator)
Fully **deterministic** — no LLM in the math, so the same data always yields the same
score. Eight components, each scored **0–1** with its own evidence string + source IDs.

**Overall = weighted average** of the components: `Σ(weightᵢ × scoreᵢ) / Σweights`
(weights sum to 1.0). **Severity bands: high ≥ 0.66 · medium ≥ 0.33 · low < 0.33.**
Components are sorted high-to-low, so the brief leads with the top risk.

| Component | Weight | How it scores |
|---|---|---|
| **Stakeholder coverage** | 0.18 | **no Decision Maker mapped → 0.82**; DM present → 0.25; no contacts → 0.7 |
| **Account status** | 0.16 | At Risk 0.9 · Prospect 0.5 · Active 0.2 |
| **Pipeline dynamics** | 0.16 | nearest close <60d → 0.8 · <120d → 0.5 · else 0.3; no open pipeline → 0.1 |
| **Relationship recency** | 0.14 | `(days_since_contact − 30) / 150`, clamped 0–1 (30d→0, 180d→1.0) |
| **AUM vs peers** | 0.12 | `1 − percentile` within the same account *type*; Prospect/$0 AUM → 0.4 |
| **Open action items** | 0.10 | `0.3 + 0.2 × (open items from prior meetings)`, capped at 1.0 |
| **Loss history** | 0.08 | any Lost opp in trailing 12 months → 0.6; else 0.1 |
| **Consultant influence** | 0.06 | external consultant (Mercer/Aon/…) → 0.5; In-house → 0.15 |

"Prob-weighted pipeline" = Σ(mandate size × probability). Peer percentile = fraction
of same-type peers with ≤ this account's AUM.

**Calderon (ACC-1002) live numbers:** coverage **82** (no DM; 2 Gatekeeper + 1 Influencer),
pipeline **80** ($688mm prob-weighted, nearest close 26d), open actions **70** (0.3 + 0.2×2),
status **50** (Prospect), consultant **50** (Mercer).

## The accuracy guarantee (why it won't hallucinate)
Three layers:
1. **Deterministic scoring** — risk numbers come from the data, never the model.
2. **Fact-check guard** — every LLM sentence (headline, risk explanations, talking points)
   survives only if **(a) every cited source ID is real** for that account, and
   **(b) every number in the text appears in the grounded context** (risk evidence,
   AUM, opp sizes/probabilities, meeting facts). Decimals normalized (946.0 ≈ 946).
   Fail either check → the sentence is dropped.
3. **Template fallback** — if the model returns nothing usable, deterministic templates
   carry the brief. (That's what you saw live — fully grounded even with the free model.)
Plus the agent's system prompt **forces a tool call** for any account/person/meeting/risk
question, so it can't answer from thin air.

## Architecture & data flow
- **Source of truth:** `Capital_Group_CRM_mock.xlsx` — 25 accounts, 50 contacts, 29 pipeline,
  69 activities (synthetic; account types + CG strategy names are real/public) — joined on
  Account ID / Name. Plus synthetic **prior-meeting fixtures** in `backend/data/generated/meetings/`.
- **Two-model split (parallelized in dev):**
  - **OpenRouter** (runtime) — the agent + brief phrasing, via a TLS-bypass for the corporate proxy.
  - **Ollama** (offline, local, GPU-less) — generated the prior-meeting transcripts without burning API credits.
- **The agent:** a LangChain **ReAct agent** with per-thread memory, exposed at **`POST /api/chat`**.
  Same endpoint backs the main Sage chat *and* the in-chat Briefing panel.
- **Grounded in 3 sources via tools:** CRM (`get_account_brief`, `get_participant_card`),
  **prior meetings** (`get_meeting_history`), and the **live in-progress conversation**
  (`get_current_meeting`).
- **Brief document:** `GET /api/accounts/{id}/brief` → structured one-pager; **cached** (first ~60s, then instant).

## Numbers to drop on stage (the Calderon money shot)
The agent answered *"$946mm combined AUM"* by summing two real mandates — **OPP-3002 $345.6mm
+ OPP-3003 $600.5mm** — and the guard *allowed* it because both numbers are in the data.
That's the story: **it does real arithmetic on grounded facts, and the guard is what
distinguishes a correct computed number from a hallucinated one.**

## Likely judge questions → crisp answers
- **"How do you stop hallucination?"** → Deterministic risk math + a fact-check guard that
  verifies every number and source ID + forced tool use + template fallback. The model
  physically can't surface a number that isn't in the data.
- **"Why these weights?"** → Domain heuristic — coverage, status, pipeline weighted highest
  (what actually sinks institutional mandates). Tunable in `config.RISK_WEIGHTS`. Honest POC,
  not yet calibrated on win/loss outcomes.
- **"Is the data real?"** → No — synthetic/mock. Account types and Capital Group strategy
  names are real/public; clients, people, numbers are fictional.
- **"Why two models?"** → Cost + offline: OpenRouter for runtime quality, Ollama for bulk
  transcript generation locally without API spend.
