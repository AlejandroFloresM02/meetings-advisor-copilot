# Linting & formatting hooks — design

**Date:** 2026-06-05
**Branch:** v2
**Status:** approved

## Goal

A clean, standardized codebase on the `v2` branch enforced automatically at
commit time, covering both the Python backend and the React UI.

## Decisions (locked in brainstorming)

| Decision | Choice |
|----------|--------|
| Enforcement | `pre-commit` framework driving both ruff and eslint |
| Ruff ruleset | Strict (broad selection) |
| Python scope | Whole repo (`backend/`, `OpenRouter_Agent/`, `scripts/`) |
| JS tooling | Keep eslint, **add Prettier** |

Work is done on a `hooks-setup` worktree branched off `v2` HEAD, then
fast-forwarded onto `v2` (the harness requires background edits to land in a
worktree; `v2` is 3 commits ahead of `origin/main`, so the worktree is based on
the local `v2` HEAD rather than the default `origin/main`).

## Components

### 1. Python — ruff (lint + format)

Root **`ruff.toml`** (leaves `backend/pyproject.toml` for pytest untouched,
covers the whole repo from one place):

- `target-version = "py312"` (langchain-openrouter requires 3.12), `line-length = 88`.
- **Strict select:** `E,W,F,I,N,UP,B,C4,SIM,PIE,RET,RSE,TID,ICN,PT,S,A,RUF`.
- **Ignores so "strict" is not "noisy":**
  - `E501` — line length is owned by the formatter (and `prompts.py` has long
    prompt strings the formatter will not wrap).
  - `B008` — FastAPI `Depends()` in argument defaults is idiomatic.
- **Per-file ignores:**
  - tests → `S101` (allow `assert`).
  - `__init__.py` → `F401` (re-exports).
  - the two `verify=False` TLS-workaround files (`backend/app/llm/openrouter_client.py`,
    `OpenRouter_Agent/agent.py`) → `S501` (intentional POC unblock, see CLAUDE.md).
- `[format]` — ruff format with default double-quote style.
- `extend-exclude` — `backend/data`, `*.xlsx`, `.venv`, `node_modules`, `dist`, `build`.

### 2. JS — eslint (existing) + Prettier (new), UI only

- `UI/package.json` — add `prettier` + `eslint-config-prettier` devDeps;
  add `format` / `format:check` scripts.
- `UI/eslint.config.js` — append `eslint-config-prettier` so eslint and Prettier
  do not conflict; keep existing react-hooks / react-refresh rules.
- `UI/.prettierrc.json` — `semi: false`, `singleQuote: true` to match the
  existing UI style (minimizes the reformat diff); `.prettierignore` for `dist`.

### 3. The hook — root `.pre-commit-config.yaml`

- **ruff:** `astral-sh/ruff-pre-commit` → `ruff` (lint, `--fix`) + `ruff-format`.
  Self-contained, pre-commit-managed, cross-platform (no bash).
- **eslint + prettier:** `language: system` local hooks invoking
  `npm --prefix UI run lint` / `npm --prefix UI run format`. `npm --prefix` runs
  with cwd = `UI/`, so it resolves `UI/node_modules` and the flat config — no bash,
  works on Windows (the team's environment per CLAUDE.md).
- **Light hygiene** (`pre-commit/pre-commit-hooks`): `trailing-whitespace`,
  `end-of-file-fixer`, `check-merge-conflict`, `check-yaml`, `check-toml` —
  excluding `backend/data/` and `*.xlsx`.

### 4. Activation + one-time cleanup

- Root `requirements-dev.txt` (`pre-commit`, `ruff`) for manual/editor/CI use.
- `npm install` in `UI/` to pull in Prettier.
- `pre-commit install` to wire the git hook.
- One-time `pre-commit run --all-files` to reformat the existing tree. **Strict +
  whole-repo means a sizable formatting/import diff and possibly a few manual
  fixes** — that is the intended clean baseline.

## Verification

- `pre-commit run --all-files` is fully green.
- `pytest` (backend) passes after the cleanup (formatting/import changes did not
  break anything).
- `npm run build` and `npm run lint` (UI) pass.

## Commits

1. config + dev deps + docs (this spec, CLAUDE.md update).
2. one-time formatting/lint cleanup of the existing tree.

## Out of scope

- CI workflow (local hooks only for now).
- Type checking (mypy / TypeScript strictness).
- Refactoring beyond what the linters require.
