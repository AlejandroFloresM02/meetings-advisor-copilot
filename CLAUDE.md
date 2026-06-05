# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **pre-meeting brief "copilot"** for **Capital Group institutional relationship managers**. Given a client account, it generates a one-page brief — relationship snapshot, talking points, and risk flags — so the RM walks into a pension/endowment/insurance client meeting with full context.

This repo is **backend-focused**: it owns data ingestion, brief generation, factual-accuracy guarding, and a JSON API. The **UI is built separately by teammates** (a React app) and integrated later. The API's JSON brief contract is therefore the most important interface in the project — it is the seam where backend and UI meet.

The data is **mock/synthetic** (see below). No real client data is used; "accuracy" means every statement in a brief traces back to a fact in the mock dataset.

## Current repository state (important — README is partly aspirational)

What actually exists today:
- `Capital_Group_CRM_mock.xlsx` — the mock CRM dataset (the source of truth for briefs).
- `OpenRouter_Agent/` — a standalone LangChain + OpenRouter chat agent (the reusable LLM-access pattern).
- `README.md` — repo title only.

What `OpenRouter_Agent/README.md` and `requirements.txt` *reference but do not yet contain*: a FastAPI `server.py` and a React `UI/` directory, and a pre-created `.venv`. **None of these exist yet.** Treat them as the intended direction, not present code. The repo will be reorganized as the backend is built out.

## Commands (Windows / PowerShell)

The OpenRouter agent is the only runnable code today. Python 3.12 is required (`langchain-openrouter` does not support 3.9).

```powershell
# From OpenRouter_Agent/ — create the venv (does NOT exist yet despite the README)
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# API key: OpenRouter_Agent/.env must contain OPENROUTER_API_KEY=<key>
# Run the interactive agent REPL
.\.venv\Scripts\python.exe agent.py
```

Intended (per README/requirements, once `server.py` and `UI/` are built):
```powershell
# Backend API
.\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
# Frontend (separate terminal)
cd UI; npm install; npm run dev   # Vite dev server, proxies /api/* to :8000
```

## Linting & formatting

Ruff (Python, whole repo) plus eslint + Prettier (the `UI/` React app) are
enforced at commit time via [pre-commit](https://pre-commit.com). Configs live in
`ruff.toml`, `.pre-commit-config.yaml`, `UI/.prettierrc.json`, and
`UI/eslint.config.js`.

One-time setup (PowerShell or bash):

```
pip install -r requirements-dev.txt   # installs ruff + pre-commit
pre-commit install                    # wires the git pre-commit hook
cd UI                                 # eslint + prettier are UI/ devDeps
npm install
```

Run manually:

```
pre-commit run --all-files            # all hooks across the repo
ruff check . --fix                    # Python lint (auto-fix)
ruff format .                         # Python format
npm --prefix UI run lint              # eslint
npm --prefix UI run format            # prettier --write
```

- Ruff is **strict** (broad rule selection). `E501` (line length) is delegated to
  the formatter, and the two intentional `verify=False` files are exempt from the
  `S501` security rule via per-file-ignores in `ruff.toml`.
- The eslint/prettier pre-commit hooks call the `UI/` npm scripts, so
  `npm install` in `UI/` is required for them to run.

The backend has a pytest suite: `cd backend; pytest` (17 tests).

## LLM access — the corporate TLS workaround (critical, non-obvious)

LLM calls go through **OpenRouter** via `langchain-openrouter`'s `ChatOpenRouter`. The environment sits behind a corporate proxy that breaks TLS, so `OpenRouter_Agent/agent.py` defines:

- **`CertificateBypassingChatOpenRouter`** — a `ChatOpenRouter` subclass that overrides `_build_client()` to pass `httpx.Client(verify=False)` (and an async variant), disabling TLS certificate verification. This is what makes calls succeed here; a plain `ChatOpenRouter` fails with SSL errors.

Other specifics:
- Model is the `MODEL` constant in `agent.py` (currently `poolside/laguna-m.1:free`, a free OpenRouter model). Swap here to change models.
- Tools are plain functions decorated with `@tool`, collected in the `TOOLS` list; the agent is built with `create_agent(...)` and uses an `InMemorySaver` checkpointer keyed by `thread_id` for per-session memory.
- `OPENROUTER_API_KEY` is loaded from `OpenRouter_Agent/.env` via `python-dotenv`. `.env` is gitignored.

⚠️ `verify=False` disables certificate validation (MITM-exposed). It is a POC unblock only. Before anything real, replace it by pointing httpx/requests at the corporate root CA bundle (e.g. `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE`, or `verify=<ca-bundle-path>`).

## Mock data — the grounding source of truth

`Capital_Group_CRM_mock.xlsx` (synthetic; account types and Capital Group strategy names are real/public, everything else fictional). Sheets:

- **Accounts** (25) — `Account ID` (ACC-1001…1025), name, `Type` (Public Pension DB, Corporate DB/DC, Endowment, Insurance General Account, Sovereign, Sub-Advisory, Healthcare, Taft-Hartley), `AUM with CG ($mm)`, `Tier` (Strategic/Core/Developing), `Client Since`, `Primary Strategy`, `Relationship Mgr`, `Consultant` (In-house, Mercer, Aon, NEPC, RVK, WTW, Callan, Verus), `Status` (Active/Prospect/At Risk).
- **Contacts** (50) — people per account with `Role` (Decision Maker / Gatekeeper / Influencer), title, `Last Contacted`.
- **Pipeline** (29) — open/closed mandate opportunities: `Strategy`, `Mandate Size ($mm)`, `Stage` (Prospecting → Qualification → RFP Submitted → Finals Presentation → Due Diligence → Won/Lost), `Probability`, `Expected Close`, `Owner`.
- **Activities** (69) — interaction log: `Date`, `Type` (Meeting, Call, Email, Conference, Portfolio Review, Webinar), `Subject`, `Next Step`.
- **AUM Summary** / **Team & Org Chart** — roll-ups and the internal CG team hierarchy.

Sheets join on `Account ID` / `Account Name`. Reading the xlsx needs `openpyxl` (and/or `pandas`) — **not yet in `requirements.txt`**; add it when building the ingestion layer.

**Accuracy principle:** briefs may only state facts present in these sheets. Risk flags should be computed deterministically from the columns; the LLM is used to phrase talking points and must not introduce numbers or claims absent from the data.

## Gotchas

- Files placed in this folder may not appear in `git status` immediately (OneDrive Files-On-Demand); `git add` explicitly when committing.
- The live `OPENROUTER_API_KEY` is present in `OpenRouter_Agent/.env`. It is gitignored, but if that file ever came from a pushed/public source, rotate the key.
