# V2 Grounded Brief — A1: Deterministic Data Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic, fully-tested data foundation for the V2 grounded pre-meeting brief — typed domain models with provenance, a committed snapshot corpus, a repository, a derived analytics layer (risk / peers / cost-effectiveness / deltas), a provenance-aware fact-check guard, and a deterministic insight-unit brief assembler — with zero LLM or network dependencies.

**Architecture:** Pure-Python library under `backend/app/`. Real client data lives as committed JSON **snapshots** (the trusted corpus from spec §4); a loader hydrates them into typed pydantic models; a repository serves them; a deterministic `derived/` layer computes risk/peer/cost/delta facts; a `guard` enforces that any number traces to a provenance-tagged fact; a `contract/` layer assembles ranked `InsightUnit`s into a `Brief` (the template/fallback path — the LLM-phrased path is sub-project B). One hand-authored CalPERS snapshot makes everything testable today.

**Tech Stack:** Python 3.12, pydantic v2, pytest. (macOS / zsh. No pandas/openpyxl — V2 grounds in JSON snapshots, not the xlsx. No LLM/httpx in A1.)

**Spec:** `docs/superpowers/specs/2026-06-04-v2-grounded-brief-data-foundation-design.md`

---

## Conventions

- All commands run **from `backend/`** with the venv interpreter `.venv/bin/python`.
- **Every `git commit` below must end with the trailer** (omitted from the per-task commands for brevity):
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- TDD: write the failing test → run it red → minimal implementation → run it green → commit.

## File structure (A1)

```
backend/
  pyproject.toml                 # MODIFY: pytest config (verify)
  requirements.txt               # REWRITE: slim to V2 core deps
  app/
    __init__.py                  # keep (empty)
    config.py                    # REWRITE: V2 paths (snapshots dir), NOW, risk weights
    provenance.py                # CREATE: Provenance tag + helpers
    domain/models.py             # REWRITE: V2 taxonomy + content-contract types
    data/snapshot.py             # CREATE: Snapshot model + load/parse
    data/repository.py           # REWRITE: repository over snapshots
    derived/__init__.py          # CREATE (empty)
    derived/risk.py              # CREATE: deterministic risk engine
    derived/peers.py             # CREATE: percentile / peer-median
    derived/cost.py              # CREATE: cost-effectiveness (net value added vs excess cost)
    derived/deltas.py            # CREATE: snapshot-over-snapshot deltas
    guard.py                     # CREATE: provenance-aware fact-check guard
    contract/__init__.py         # CREATE (empty)
    contract/insight.py          # CREATE: InsightUnit + deterministic Brief assembler
  data/snapshots/CALPERS.json    # CREATE: hand-authored sample snapshot (committed)
  tests/
    __init__.py                  # keep
    conftest.py                  # REWRITE: V2 fixtures
    test_models.py               # CREATE
    test_snapshot.py             # CREATE
    test_repository.py           # CREATE
    test_risk.py                 # CREATE
    test_peers_cost.py           # CREATE
    test_deltas.py               # CREATE
    test_guard.py                # CREATE
    test_contract.py             # CREATE
```

**Removed in Task 0** (superseded by sub-projects B/C/D; preserved on `main` + git history):
`app/risk/`, `app/data/loader.py`, `app/generation/`, `app/agent/`, `app/api/`, `app/main.py`,
`backend/scripts/`, `backend/preview.html`, `backend/data/generated/`, and V1 tests
`test_loader/brief/participant/generator/api/risk/guard`.
**Kept:** `app/llm/` (no model import; needed in sub-project B).

> ⚠️ **Decision flagged for the owner:** Task 0 does a clean V2 teardown of V1's upper layers. If you'd rather keep V1 running in parallel, say so and I'll rework Task 0 to build A1 in a parallel package instead.

## Canonical signatures (use these exact names across tasks)

```python
# provenance.py
Provenance(kind: Literal["public","cg_house_view","synthetic","derived"],
           url: str|None=None, fetched_at: date|None=None, note: str|None=None)

# domain/models.py — value objects
Metric(key: str, value: float, unit: str|None, as_of: date|None, provenance: Provenance)
Evidence(text: str, provenance: Provenance)
InsightUnit(insight: str, why_now: str, evidence: list[Evidence], play: str|None=None,
            freshness: Literal["frozen","live"]="frozen", severity: str|None=None, score: float|None=None)
Brief(client_id: str, scenario: str, bluf: str, sections: dict[str, list[InsightUnit]], meta: dict)
# domain/models.py — entities
AllocationSlice(asset_class: str, target_pct: float|None, actual_pct: float|None)
Institution(id, name, type, plan_assets_mm: float|None, fiscal_year: int|None,
            funded_ratio: float|None, assumed_return: float|None,
            allocation: list[AllocationSlice], policy_benchmark: str|None, provenance: Provenance)
GovernanceSeat(id, title, remit: str|None, committee: str|None, decides: str|None,
               priorities: list[str], provenance: Provenance)
Person(id, name, seat_id, background: str|None, provenance: Provenance)
CGMandate(id, strategy, vehicle: str|None, size_mm: float, fee_bps: float|None,
          inception: date|None, net_excess_bps: float|None, information_ratio: float|None,
          down_capture: float|None, benchmark: str|None, provenance: Provenance)
Opportunity(id, strategy, size_mm: float, stage, probability: float,
            expected_close: date|None, owner: str|None, provenance: Provenance)
RelationshipMeta(rm: str|None, tier: str|None, consultant: str|None, status: str|None,
                 client_since: int|None, provenance: Provenance)
InvestmentAction(id, date: date|None, kind: str, manager: str|None,
                 asset_class: str|None, detail: str|None, provenance: Provenance)
Interaction(id, date: date|None, kind: str, summary: str,
            open_action_items: list[str], provenance: Provenance)
Meeting(id, date: date, purpose: str, objective: str|None,
        scenario: Literal["portfolio_review","finals","at_risk_save","relationship_review"],
        seat_ids: list[str], provenance: Provenance)
# derived outputs
RiskFlag(key, title, severity: str, score: float, evidence: str, provenance: Provenance)
CostEffectiveness(net_value_added_bps: float|None, excess_cost_bps: float|None,
                  verdict: str, evidence: str)
Delta(field: str, before, after, direction: str, summary: str)

# data/snapshot.py
Snapshot(client_id, captured_at: date, institution: Institution, seats: list[GovernanceSeat],
         people: list[Person], actions: list[InvestmentAction], mandates: list[CGMandate],
         pipeline: list[Opportunity], relationship: RelationshipMeta|None,
         interactions: list[Interaction], meetings: list[Meeting])
load_snapshot(path: Path) -> Snapshot
load_all_snapshots(dir: Path) -> dict[str, Snapshot]

# data/repository.py
Repository(snapshots: dict[str, Snapshot])
Repository.get(client_id) -> Snapshot|None
Repository.all() -> list[Snapshot]
Repository.institutions() -> list[Institution]
load_repository(dir: Path) -> Repository

# derived/
compute_risk(snap: Snapshot, repo: Repository, now: date) -> list[RiskFlag]
severity_band(score: float) -> str
percentile_rank(values: list[float], value: float) -> float
peer_median(values: list[float]) -> float|None
compute_cost_effectiveness(snap: Snapshot, repo: Repository) -> CostEffectiveness
compute_deltas(prev: Snapshot, curr: Snapshot) -> list[Delta]

# guard.py
extract_numbers(text: str) -> set[str]
evidence_numbers(evidence: list[Evidence]) -> set[str]
unit_supported(u: InsightUnit) -> bool
guard_units(units: list[InsightUnit]) -> list[InsightUnit]

# contract/insight.py
build_brief(snap: Snapshot, repo: Repository, now: date) -> Brief
```

---

# Task 0: Scaffold V2 + slim deps + remove superseded V1 modules

**Files:**
- Modify: `backend/requirements.txt`, `backend/pyproject.toml`
- Remove: V1 upper layers (see below)
- Create: `backend/app/derived/__init__.py`, `backend/app/contract/__init__.py` (empty)

- [ ] **Step 1: Slim `backend/requirements.txt`**

```
# V2 data core (sub-project A1) — pure Python, no LLM/network.
pydantic>=2
python-dotenv==1.2.2
pytest
```

- [ ] **Step 2: Verify `backend/pyproject.toml`**

Ensure it contains:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Create the venv and install (from `backend/`)**

Run:
```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```
Expected: `pydantic`, `pytest`, `python-dotenv` install cleanly.

- [ ] **Step 4: Remove superseded V1 modules + create new package dirs**

Run:
```bash
git rm -r app/risk app/generation app/agent app/api app/main.py app/data/loader.py \
          scripts preview.html data/generated \
          tests/test_loader.py tests/test_brief.py tests/test_participant.py \
          tests/test_generator.py tests/test_api.py tests/test_risk.py tests/test_guard.py
mkdir -p app/derived app/contract data/snapshots
touch app/derived/__init__.py app/contract/__init__.py
```
(If a path is already absent, drop it from the command.) `app/llm/` is intentionally kept.

- [ ] **Step 5: Verify pytest still loads (no tests yet)**

Run: `.venv/bin/python -m pytest`
Expected: "no tests ran" (exit 5) — config loads, old tests gone.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(v2): scaffold A1 data core, slim deps, remove superseded V1 layers"
```

---

# Task 1: Provenance + domain models

**Files:**
- Create: `backend/app/provenance.py`, `backend/tests/test_models.py`
- Rewrite: `backend/app/domain/models.py`

- [ ] **Step 1: Write the failing test `tests/test_models.py`**

```python
from datetime import date

from app.provenance import Provenance
from app.domain.models import (
    Institution, AllocationSlice, GovernanceSeat, CGMandate, Meeting,
    Metric, Evidence, InsightUnit, Brief,
)


def test_provenance_requires_kind():
    p = Provenance(kind="public", url="https://example.gov/acfr", fetched_at=date(2026, 6, 1))
    assert p.kind == "public" and p.url.endswith("acfr")


def test_institution_holds_allocation_and_provenance():
    inst = Institution(
        id="CALPERS", name="CalPERS", type="public_pension",
        plan_assets_mm=502000.0, fiscal_year=2025, funded_ratio=0.75, assumed_return=0.068,
        allocation=[AllocationSlice(asset_class="Fixed Income", target_pct=30.0, actual_pct=28.0)],
        policy_benchmark="CalPERS Policy Benchmark",
        provenance=Provenance(kind="public", url="https://calpers.ca.gov"),
    )
    assert inst.allocation[0].asset_class == "Fixed Income"
    assert inst.provenance.kind == "public"


def test_meeting_scenario_is_constrained():
    import pydantic
    m = Meeting(id="MTG-1", date=date(2026, 6, 5), purpose="Review", objective="Defend mandate",
                scenario="portfolio_review", seat_ids=["SEAT-CIO"],
                provenance=Provenance(kind="synthetic"))
    assert m.scenario == "portfolio_review"
    try:
        Meeting(id="MTG-2", date=date(2026, 6, 5), purpose="x", objective=None,
                scenario="bogus", seat_ids=[], provenance=Provenance(kind="synthetic"))
        assert False, "invalid scenario should raise"
    except pydantic.ValidationError:
        pass


def test_insight_unit_and_brief_compose():
    u = InsightUnit(
        insight="Fee pressure threatens the Core Plus mandate.",
        why_now="The IC opened a cost review.",
        evidence=[Evidence(text="Mandate fee 38bps", provenance=Provenance(kind="synthetic"))],
        play="Offer the SMA breakpoint.", severity="high", score=0.8,
    )
    b = Brief(client_id="CALPERS", scenario="portfolio_review", bluf="Defend the mandate.",
              sections={"risks": [u]}, meta={"generated_at": "2026-06-04"})
    assert b.sections["risks"][0].insight.startswith("Fee pressure")
    assert b.bluf
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_models.py -q`
Expected: FAIL (`ModuleNotFoundError: app.provenance`).

- [ ] **Step 3: Implement `app/provenance.py`**

```python
"""Provenance tag attached to every fact in the V2 data model."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

ProvenanceKind = Literal["public", "cg_house_view", "synthetic", "derived"]


class Provenance(BaseModel):
    kind: ProvenanceKind
    url: Optional[str] = None
    fetched_at: Optional[date] = None
    note: Optional[str] = None
```

- [ ] **Step 4: Implement `app/domain/models.py`**

```python
"""V2 entity taxonomy (spec §5) + content-contract types (spec §9).

Every entity carries a Provenance tag. Numbers that must be citable are carried
as Metric/Evidence so the guard (app/guard.py) can verify them.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.provenance import Provenance


# ---- value objects ---------------------------------------------------------
class Metric(BaseModel):
    key: str
    value: float
    unit: Optional[str] = None          # "%", "bps", "$mm", "ratio"
    as_of: Optional[date] = None
    provenance: Provenance


class Evidence(BaseModel):
    text: str
    provenance: Provenance


class InsightUnit(BaseModel):
    insight: str
    why_now: str
    evidence: list[Evidence] = Field(default_factory=list)
    play: Optional[str] = None
    freshness: Literal["frozen", "live"] = "frozen"
    severity: Optional[str] = None
    score: Optional[float] = None


class Brief(BaseModel):
    client_id: str
    scenario: str
    bluf: str
    sections: dict[str, list[InsightUnit]] = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


# ---- entities --------------------------------------------------------------
class AllocationSlice(BaseModel):
    asset_class: str
    target_pct: Optional[float] = None
    actual_pct: Optional[float] = None


class Institution(BaseModel):
    id: str
    name: str
    type: str
    plan_assets_mm: Optional[float] = None
    fiscal_year: Optional[int] = None
    funded_ratio: Optional[float] = None
    assumed_return: Optional[float] = None
    allocation: list[AllocationSlice] = Field(default_factory=list)
    policy_benchmark: Optional[str] = None
    provenance: Provenance


class GovernanceSeat(BaseModel):
    id: str
    title: str
    remit: Optional[str] = None
    committee: Optional[str] = None
    decides: Optional[str] = None
    priorities: list[str] = Field(default_factory=list)
    provenance: Provenance


class Person(BaseModel):
    id: str
    name: str               # imagined persona — no real PII (spec §8)
    seat_id: str
    background: Optional[str] = None
    provenance: Provenance


class CGMandate(BaseModel):
    id: str
    strategy: str
    vehicle: Optional[str] = None
    size_mm: float = 0.0
    fee_bps: Optional[float] = None
    inception: Optional[date] = None
    net_excess_bps: Optional[float] = None
    information_ratio: Optional[float] = None
    down_capture: Optional[float] = None
    benchmark: Optional[str] = None
    provenance: Provenance


class Opportunity(BaseModel):
    id: str
    strategy: str
    size_mm: float = 0.0
    stage: str
    probability: float = 0.0
    expected_close: Optional[date] = None
    owner: Optional[str] = None
    provenance: Provenance


class RelationshipMeta(BaseModel):
    rm: Optional[str] = None
    tier: Optional[str] = None
    consultant: Optional[str] = None
    status: Optional[str] = None
    client_since: Optional[int] = None
    provenance: Provenance


class InvestmentAction(BaseModel):
    id: str
    date: Optional[date] = None
    kind: str               # "hire" | "terminate" | "search" | "watch"
    manager: Optional[str] = None
    asset_class: Optional[str] = None
    detail: Optional[str] = None
    provenance: Provenance


class Interaction(BaseModel):
    id: str
    date: Optional[date] = None
    kind: str
    summary: str
    open_action_items: list[str] = Field(default_factory=list)
    provenance: Provenance


class Meeting(BaseModel):
    id: str
    date: date
    purpose: str
    objective: Optional[str] = None
    scenario: Literal["portfolio_review", "finals", "at_risk_save", "relationship_review"]
    seat_ids: list[str] = Field(default_factory=list)
    provenance: Provenance


# ---- derived outputs -------------------------------------------------------
class RiskFlag(BaseModel):
    key: str
    title: str
    severity: str
    score: float
    evidence: str
    provenance: Provenance


class CostEffectiveness(BaseModel):
    net_value_added_bps: Optional[float] = None
    excess_cost_bps: Optional[float] = None
    verdict: str
    evidence: str


class Delta(BaseModel):
    field: str
    before: Any = None
    after: Any = None
    direction: str          # "up" | "down" | "changed"
    summary: str
```

- [ ] **Step 5: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_models.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add app/provenance.py app/domain/models.py tests/test_models.py
git commit -m "feat(v2): provenance + domain models (entities + content-contract types)"
```

---

# Task 2: Snapshot schema + hand-authored CalPERS sample

**Files:**
- Create: `backend/app/data/snapshot.py`, `backend/data/snapshots/CALPERS.json`, `backend/tests/test_snapshot.py`

- [ ] **Step 1: Write the failing test `tests/test_snapshot.py`**

```python
from pathlib import Path

from app.data.snapshot import load_snapshot, load_all_snapshots

SNAP_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshots"


def test_calpers_snapshot_loads_typed():
    snap = load_snapshot(SNAP_DIR / "CALPERS.json")
    assert snap.client_id == "CALPERS"
    assert snap.institution.name == "CalPERS"
    assert snap.institution.funded_ratio == 0.75
    assert snap.institution.provenance.kind == "public"
    # synthetic layer present and tagged
    mandate = snap.mandates[0]
    assert mandate.fee_bps == 38.0
    assert mandate.provenance.kind == "synthetic"
    # the upcoming meeting drives scenario
    assert snap.meetings[0].scenario == "portfolio_review"
    # personas are synthetic over real seats
    person = snap.people[0]
    assert person.provenance.kind == "synthetic"
    assert any(s.id == person.seat_id for s in snap.seats)


def test_load_all_snapshots_indexes_by_client():
    snaps = load_all_snapshots(SNAP_DIR)
    assert "CALPERS" in snaps
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -q`
Expected: FAIL (`ModuleNotFoundError: app.data.snapshot`).

- [ ] **Step 3: Implement `app/data/snapshot.py`**

```python
"""The committed per-client snapshot (spec §4) — the trusted corpus the runtime reads."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain.models import (
    CGMandate, GovernanceSeat, Institution, InvestmentAction, Interaction,
    Meeting, Opportunity, Person, RelationshipMeta,
)


class Snapshot(BaseModel):
    client_id: str
    captured_at: date
    institution: Institution
    seats: list[GovernanceSeat] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)
    actions: list[InvestmentAction] = Field(default_factory=list)
    mandates: list[CGMandate] = Field(default_factory=list)
    pipeline: list[Opportunity] = Field(default_factory=list)
    relationship: RelationshipMeta | None = None
    interactions: list[Interaction] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)


def load_snapshot(path: Path) -> Snapshot:
    return Snapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_all_snapshots(directory: Path) -> dict[str, Snapshot]:
    out: dict[str, Snapshot] = {}
    for fp in sorted(Path(directory).glob("*.json")):
        snap = load_snapshot(fp)
        out[snap.client_id] = snap
    return out
```

- [ ] **Step 4: Create `backend/data/snapshots/CALPERS.json`**

> Public fields illustrative pending real ingestion (A2); `public` provenance carries the source URL. CG layer is `synthetic`. Personas are imagined names over real seats.

```json
{
  "client_id": "CALPERS",
  "captured_at": "2026-06-01",
  "institution": {
    "id": "CALPERS", "name": "CalPERS", "type": "public_pension",
    "plan_assets_mm": 502000.0, "fiscal_year": 2025,
    "funded_ratio": 0.75, "assumed_return": 0.068,
    "allocation": [
      {"asset_class": "Global Equity", "target_pct": 42.0, "actual_pct": 44.0},
      {"asset_class": "Fixed Income", "target_pct": 30.0, "actual_pct": 28.0},
      {"asset_class": "Private Equity", "target_pct": 13.0, "actual_pct": 15.0},
      {"asset_class": "Private Credit", "target_pct": 4.0, "actual_pct": 1.5}
    ],
    "policy_benchmark": "CalPERS Policy Benchmark",
    "provenance": {"kind": "public", "url": "https://www.calpers.ca.gov", "fetched_at": "2026-06-01"}
  },
  "seats": [
    {"id": "SEAT-CIO", "title": "Chief Investment Officer", "remit": "Total fund",
     "committee": "Investment Committee", "decides": "Manager retention & allocation",
     "priorities": ["cost-efficiency", "total-fund risk"],
     "provenance": {"kind": "public", "url": "https://www.calpers.ca.gov/about/board", "fetched_at": "2026-06-01"}},
    {"id": "SEAT-FI", "title": "Head of Fixed Income", "remit": "Fixed income mandates",
     "committee": "Investment Committee", "decides": "Fixed income manager relationships",
     "priorities": ["downside protection", "fee value"],
     "provenance": {"kind": "public", "url": "https://www.calpers.ca.gov/about/board", "fetched_at": "2026-06-01"}}
  ],
  "people": [
    {"id": "P-1", "name": "Jordan Avery", "seat_id": "SEAT-CIO",
     "background": "Two decades in public-fund total-portfolio management.",
     "provenance": {"kind": "synthetic"}},
    {"id": "P-2", "name": "Morgan Reyes", "seat_id": "SEAT-FI",
     "background": "Fixed-income allocator focused on core-plus mandates.",
     "provenance": {"kind": "synthetic"}}
  ],
  "actions": [
    {"id": "ACT-1", "date": "2026-05-12", "kind": "watch", "manager": "A small-cap equity manager",
     "asset_class": "Global Equity", "detail": "Placed on watch after 3 quarters of underperformance.",
     "provenance": {"kind": "public", "url": "https://www.pionline.com", "fetched_at": "2026-06-01"}},
    {"id": "ACT-2", "date": "2026-05-20", "kind": "search", "manager": null,
     "asset_class": "Private Credit", "detail": "Notice of search to fund the private-credit target.",
     "provenance": {"kind": "public", "url": "https://www.calpers.ca.gov", "fetched_at": "2026-06-01"}}
  ],
  "mandates": [
    {"id": "CGM-1", "strategy": "Core Plus Income", "vehicle": "Separate Account",
     "size_mm": 600.5, "fee_bps": 38.0, "inception": "2019-03-01",
     "net_excess_bps": 62.0, "information_ratio": 0.71, "down_capture": 0.83,
     "benchmark": "Bloomberg US Aggregate", "provenance": {"kind": "synthetic"}}
  ],
  "pipeline": [
    {"id": "OPP-1", "strategy": "Private Credit", "size_mm": 250.0, "stage": "Qualification",
     "probability": 0.4, "expected_close": "2026-09-30", "owner": "Diane Okafor",
     "provenance": {"kind": "synthetic"}}
  ],
  "relationship": {"rm": "Diane Okafor", "tier": "Strategic", "consultant": "Mercer",
                   "status": "Active", "client_since": 2009, "provenance": {"kind": "synthetic"}},
  "interactions": [
    {"id": "INT-1", "date": "2026-04-22", "kind": "Portfolio Review",
     "summary": "Reviewed Core Plus performance; discussed fee schedule.",
     "open_action_items": ["Send the SMA breakpoint schedule to Mercer"],
     "provenance": {"kind": "synthetic"}}
  ],
  "meetings": [
    {"id": "MTG-1", "date": "2026-06-05", "purpose": "Quarterly portfolio review",
     "objective": "Defend the Core Plus mandate amid the cost review",
     "scenario": "portfolio_review", "seat_ids": ["SEAT-CIO", "SEAT-FI"],
     "provenance": {"kind": "synthetic"}}
  ]
}
```

- [ ] **Step 5: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/data/snapshot.py data/snapshots/CALPERS.json tests/test_snapshot.py
git commit -m "feat(v2): snapshot schema + hand-authored CalPERS sample corpus"
```

---

# Task 3: Repository + config + conftest

**Files:**
- Rewrite: `backend/app/config.py`, `backend/app/data/repository.py`, `backend/tests/conftest.py`
- Create: `backend/tests/test_repository.py`

- [ ] **Step 1: Write the failing test `tests/test_repository.py`**

```python
def test_repository_serves_snapshot(repo):
    snap = repo.get("CALPERS")
    assert snap is not None and snap.institution.name == "CalPERS"
    assert repo.get("NOPE") is None


def test_repository_lists_institutions(repo):
    insts = repo.institutions()
    assert any(i.id == "CALPERS" for i in insts)
    assert len(repo.all()) >= 1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_repository.py -q`
Expected: FAIL (`fixture 'repo' not found` or import error).

- [ ] **Step 3: Implement `app/config.py`**

```python
"""V2 config: paths + the reference 'now' date + risk weights."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")

SNAPSHOTS_DIR = Path(os.getenv("SNAPSHOTS_DIR", BACKEND_ROOT / "data" / "snapshots"))


def _now() -> date:
    y, m, d = (int(x) for x in os.getenv("NOW_DATE", "2026-06-04").split("-"))
    return date(y, m, d)


NOW: date = _now()
```

- [ ] **Step 4: Implement `app/data/repository.py`**

```python
"""In-memory repository over committed snapshots (spec §4)."""
from __future__ import annotations

from pathlib import Path

from app.data.snapshot import Snapshot, load_all_snapshots
from app.domain.models import Institution


class Repository:
    def __init__(self, snapshots: dict[str, Snapshot]):
        self.snapshots = dict(snapshots)

    def get(self, client_id: str) -> Snapshot | None:
        return self.snapshots.get(client_id)

    def all(self) -> list[Snapshot]:
        return list(self.snapshots.values())

    def institutions(self) -> list[Institution]:
        return [s.institution for s in self.snapshots.values()]


def load_repository(directory: Path) -> Repository:
    return Repository(load_all_snapshots(directory))
```

- [ ] **Step 5: Rewrite `tests/conftest.py`**

```python
import pytest

from app.config import SNAPSHOTS_DIR
from app.data.repository import load_repository


@pytest.fixture
def repo():
    return load_repository(SNAPSHOTS_DIR)


@pytest.fixture
def calpers(repo):
    return repo.get("CALPERS")
```

- [ ] **Step 6: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_repository.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/data/repository.py tests/conftest.py tests/test_repository.py
git commit -m "feat(v2): config + snapshot repository + test fixtures"
```

---

# Task 4: Derived — risk engine

**Files:**
- Create: `backend/app/derived/risk.py`, `backend/tests/test_risk.py`

- [ ] **Step 1: Write the failing test `tests/test_risk.py`**

```python
from datetime import date

from app.derived.risk import compute_risk, severity_band


def test_severity_bands():
    assert severity_band(0.9) == "high"
    assert severity_band(0.5) == "medium"
    assert severity_band(0.1) == "low"


def test_calpers_flags_are_grounded(repo, calpers):
    flags = compute_risk(calpers, repo, date(2026, 6, 4))
    keys = {f.key for f in flags}
    # underfunded (0.75) -> funded_status risk; manager on watch -> manager_watch
    assert {"funded_status", "manager_watch", "allocation_gap"} <= keys
    funded = next(f for f in flags if f.key == "funded_status")
    assert funded.severity in {"high", "medium"}
    assert "75" in funded.evidence            # cites the funded ratio
    assert funded.provenance.kind == "derived"
    # private-credit underweight (1.5 vs 4.0 target) should surface
    gap = next(f for f in flags if f.key == "allocation_gap")
    assert "Private Credit" in gap.evidence
    # flags are sorted by score desc
    assert flags == sorted(flags, key=lambda f: f.score, reverse=True)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_risk.py -q`
Expected: FAIL (`ModuleNotFoundError: app.derived.risk`).

- [ ] **Step 3: Implement `app/derived/risk.py`**

```python
"""Deterministic risk engine (spec §5⑥). Each component -> RiskFlag(score 0..1,
evidence carrying the raw numbers, derived provenance)."""
from __future__ import annotations

from datetime import date

from app.provenance import Provenance
from app.domain.models import RiskFlag

_DERIVED = Provenance(kind="derived")


def severity_band(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def _flag(key, title, score, evidence) -> RiskFlag:
    score = max(0.0, min(1.0, score))
    return RiskFlag(key=key, title=title, score=score, severity=severity_band(score),
                    evidence=evidence, provenance=_DERIVED)


def compute_risk(snap, repo, now: date) -> list[RiskFlag]:
    inst = snap.institution
    flags: list[RiskFlag] = []

    # funded status: lower funded ratio -> higher risk (1.0 at 60%, 0 at 100%)
    if inst.funded_ratio is not None:
        score = min(1.0, max(0.0, (1.0 - inst.funded_ratio) / 0.4))
        flags.append(_flag("funded_status", "Funded status", score,
                           f"Funded ratio {inst.funded_ratio * 100:.0f}% (assumed return "
                           f"{(inst.assumed_return or 0) * 100:.1f}%)."))

    # allocation gap: largest |target-actual|, weighted toward underfunded targets
    gaps = [(a, (a.target_pct or 0) - (a.actual_pct or 0)) for a in inst.allocation
            if a.target_pct is not None and a.actual_pct is not None]
    if gaps:
        a, gap = max(gaps, key=lambda t: abs(t[1]))
        score = min(1.0, abs(gap) / 5.0)
        verb = "under-allocated" if gap > 0 else "over-allocated"
        flags.append(_flag("allocation_gap", "Allocation drift", score,
                           f"{a.asset_class} {verb} by {abs(gap):.1f}pp "
                           f"(target {a.target_pct:.1f}% vs actual {a.actual_pct:.1f}%)."))

    # manager on watch / terminations in the public actions
    watch = [x for x in snap.actions if x.kind in ("watch", "terminate")]
    if watch:
        flags.append(_flag("manager_watch", "Manager under review",
                           min(1.0, 0.5 + 0.2 * len(watch)),
                           f"{len(watch)} manager(s) on watch/terminated; e.g. {watch[0].detail}"))

    # stakeholder coverage: how many attending seats lack a mapped person
    upcoming = snap.meetings[0] if snap.meetings else None
    if upcoming:
        mapped = {p.seat_id for p in snap.people}
        missing = [sid for sid in upcoming.seat_ids if sid not in mapped]
        score = 0.7 if missing else 0.2
        flags.append(_flag("coverage", "Stakeholder coverage", score,
                           f"{len(missing)} of {len(upcoming.seat_ids)} attending seats unmapped."))

    # recency of last interaction
    dated = [i.date for i in snap.interactions if i.date]
    if dated:
        days = (now - max(dated)).days
        flags.append(_flag("recency", "Relationship recency", min(1.0, max(0.0, (days - 30) / 150)),
                           f"Last interaction {days} days ago."))

    # pipeline urgency: nearest expected close
    closes = [(o.expected_close - now).days for o in snap.pipeline if o.expected_close]
    if closes:
        nearest = min(closes)
        score = 0.8 if nearest < 60 else 0.5 if nearest < 120 else 0.3
        flags.append(_flag("pipeline", "Pipeline urgency", score,
                           f"Nearest opportunity closes in {nearest} days."))

    # open action items
    open_items = [ai for i in snap.interactions for ai in i.open_action_items]
    if open_items:
        flags.append(_flag("open_actions", "Open commitments", min(1.0, 0.3 + 0.2 * len(open_items)),
                           f"{len(open_items)} open action item(s) from prior meetings."))

    flags.sort(key=lambda f: f.score, reverse=True)
    return flags
```

- [ ] **Step 4: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_risk.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/derived/risk.py tests/test_risk.py
git commit -m "feat(v2): deterministic risk engine over the snapshot model"
```

---

# Task 5: Derived — peers + cost-effectiveness (net value added)

**Files:**
- Create: `backend/app/derived/peers.py`, `backend/app/derived/cost.py`, `backend/tests/test_peers_cost.py`

- [ ] **Step 1: Write the failing test `tests/test_peers_cost.py`**

```python
from app.derived.peers import percentile_rank, peer_median
from app.derived.cost import compute_cost_effectiveness


def test_percentile_and_median():
    assert percentile_rank([10, 20, 30, 40], 30) == 0.75
    assert percentile_rank([], 5) == 0.5
    assert peer_median([10, 20, 30]) == 20
    assert peer_median([]) is None


def test_cost_effectiveness_uses_net_value_added(repo, calpers):
    ce = compute_cost_effectiveness(calpers, repo)
    # net value added derives from the mandate's net excess (62bps); fee 38bps
    assert ce.net_value_added_bps == 62.0
    assert "62" in ce.evidence and "38" in ce.evidence
    assert ce.verdict  # non-empty narrative verdict
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_peers_cost.py -q`
Expected: FAIL (`ModuleNotFoundError: app.derived.peers`).

- [ ] **Step 3: Implement `app/derived/peers.py`**

```python
"""Peer-relative helpers (spec §6G). Degenerate-safe for a single-client corpus."""
from __future__ import annotations


def percentile_rank(values: list[float], value: float) -> float:
    """Fraction of values <= value (0..1). Empty -> 0.5."""
    if not values:
        return 0.5
    return sum(1 for v in values if v <= value) / len(values)


def peer_median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
```

- [ ] **Step 4: Implement `app/derived/cost.py`**

```python
"""Cost-effectiveness in CEM terms: net value added vs excess cost (spec §6G).

net value added = the mandate's net-of-fee excess return (bps).
excess cost      = the mandate fee minus the peer-median fee (bps), when peers exist.
"""
from __future__ import annotations

from app.derived.peers import peer_median
from app.domain.models import CostEffectiveness


def compute_cost_effectiveness(snap, repo) -> CostEffectiveness:
    if not snap.mandates:
        return CostEffectiveness(net_value_added_bps=None, excess_cost_bps=None,
                                 verdict="No CG mandate on record.", evidence="")
    m = snap.mandates[0]
    nva = m.net_excess_bps

    # peer-median fee across all mandates in the corpus (same-strategy if available)
    peer_fees = [x.fee_bps for s in repo.all() for x in s.mandates
                 if x.fee_bps is not None and x.strategy == m.strategy and x.id != m.id]
    pm = peer_median(peer_fees)
    excess_cost = (m.fee_bps - pm) if (pm is not None and m.fee_bps is not None) else None

    if nva is not None and m.fee_bps is not None:
        verdict = ("Adds value net of cost" if nva > m.fee_bps
                   else "Value-add does not clear the fee")
        evidence = (f"Net value added {nva:.0f}bps vs fee {m.fee_bps:.0f}bps"
                    + (f"; fee {excess_cost:+.0f}bps vs peer median {pm:.0f}bps." if excess_cost is not None
                       else " (no peer fee benchmark yet)."))
    else:
        verdict = "Insufficient data for a cost-effectiveness verdict."
        evidence = ""
    return CostEffectiveness(net_value_added_bps=nva, excess_cost_bps=excess_cost,
                             verdict=verdict, evidence=evidence)
```

- [ ] **Step 5: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_peers_cost.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/derived/peers.py app/derived/cost.py tests/test_peers_cost.py
git commit -m "feat(v2): peer helpers + cost-effectiveness (net value added vs excess cost)"
```

---

# Task 6: Derived — snapshot-over-snapshot deltas

**Files:**
- Create: `backend/app/derived/deltas.py`, `backend/tests/test_deltas.py`

- [ ] **Step 1: Write the failing test `tests/test_deltas.py`**

```python
from app.derived.deltas import compute_deltas


def test_deltas_detect_funded_ratio_move(calpers):
    prev = calpers.model_copy(deep=True)
    prev.institution.funded_ratio = 0.72
    deltas = compute_deltas(prev, calpers)   # 0.72 -> 0.75
    funded = next(d for d in deltas if d.field == "funded_ratio")
    assert funded.direction == "up"
    assert "72" in funded.summary and "75" in funded.summary


def test_deltas_detect_new_actions(calpers):
    prev = calpers.model_copy(deep=True)
    prev.actions = []                         # all current actions are "new"
    deltas = compute_deltas(prev, calpers)
    assert any(d.field == "actions" and d.direction == "changed" for d in deltas)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_deltas.py -q`
Expected: FAIL (`ModuleNotFoundError: app.derived.deltas`).

- [ ] **Step 3: Implement `app/derived/deltas.py`**

```python
"""Period-over-period deltas between two snapshots (spec §5⑤, §9 #3)."""
from __future__ import annotations

from app.domain.models import Delta


def _num_delta(field, before, after) -> Delta | None:
    if before is None or after is None or before == after:
        return None
    direction = "up" if after > before else "down"
    return Delta(field=field, before=before, after=after, direction=direction,
                 summary=f"{field.replace('_', ' ')} moved {before} → {after}.")


def compute_deltas(prev, curr) -> list[Delta]:
    out: list[Delta] = []
    pi, ci = prev.institution, curr.institution
    for field in ("funded_ratio", "assumed_return", "plan_assets_mm"):
        d = _num_delta(field, getattr(pi, field), getattr(ci, field))
        if d:
            out.append(d)

    # new investment actions since the prior snapshot
    prev_ids = {a.id for a in prev.actions}
    new_actions = [a for a in curr.actions if a.id not in prev_ids]
    if new_actions:
        out.append(Delta(field="actions", before=len(prev.actions), after=len(curr.actions),
                         direction="changed",
                         summary=f"{len(new_actions)} new investment action(s): "
                                 f"{new_actions[0].detail}"))
    return out
```

- [ ] **Step 4: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_deltas.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/derived/deltas.py tests/test_deltas.py
git commit -m "feat(v2): snapshot-over-snapshot deltas"
```

---

# Task 7: Provenance-aware fact-check guard

**Files:**
- Create: `backend/app/guard.py`, `backend/tests/test_guard.py`

- [ ] **Step 1: Write the failing test `tests/test_guard.py`**

```python
from app.provenance import Provenance
from app.domain.models import Evidence, InsightUnit
from app.guard import extract_numbers, unit_supported, guard_units


def test_extract_numbers_strips_punctuation():
    assert {"946", "2", "80"} <= extract_numbers("~$946mm across 2 mandates at 80%")


def test_unit_supported_requires_numbers_in_evidence():
    ev = [Evidence(text="Mandate fee 38bps; net excess 62bps", provenance=Provenance(kind="synthetic"))]
    ok = InsightUnit(insight="Fee is 38bps for 62bps of value", why_now="x", evidence=ev)
    bad = InsightUnit(insight="Fee is 99bps", why_now="x", evidence=ev)   # 99 not in evidence
    assert unit_supported(ok)
    assert not unit_supported(bad)


def test_unit_with_no_evidence_is_dropped():
    naked = InsightUnit(insight="Worth $700mm", why_now="x", evidence=[])
    assert not unit_supported(naked)


def test_guard_units_filters():
    ev = [Evidence(text="38bps", provenance=Provenance(kind="synthetic"))]
    kept = guard_units([
        InsightUnit(insight="Fee 38bps", why_now="x", evidence=ev),
        InsightUnit(insight="Fee 99bps", why_now="x", evidence=ev),
    ])
    assert len(kept) == 1 and "38" in kept[0].insight
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_guard.py -q`
Expected: FAIL (`ModuleNotFoundError: app.guard`).

- [ ] **Step 3: Implement `app/guard.py`**

```python
"""Provenance-aware fact-check guard (spec §8): a hard groundedness gate, not a
hallucination eliminator. An InsightUnit survives only if every number in its
insight/why_now/play text appears in its evidence (which carries provenance)."""
from __future__ import annotations

import re

_NUM = re.compile(r"\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.findall(text or ""):
        out.add(m)
        if "." in m:
            out.add(m.split(".")[0])      # index integer part too ("946.0" -> "946")
    return out


def evidence_numbers(evidence) -> set[str]:
    nums: set[str] = set()
    for e in evidence:
        nums |= extract_numbers(e.text)
    return nums


def unit_supported(u) -> bool:
    claim_nums = extract_numbers(u.insight) | extract_numbers(u.why_now or "") | extract_numbers(u.play or "")
    if not claim_nums:
        return bool(u.evidence)           # qualitative claim still needs at least one cited fact
    return bool(u.evidence) and claim_nums <= evidence_numbers(u.evidence)


def guard_units(units) -> list:
    return [u for u in units if unit_supported(u)]
```

- [ ] **Step 4: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_guard.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/guard.py tests/test_guard.py
git commit -m "feat(v2): provenance-aware fact-check guard (groundedness gate)"
```

---

# Task 8: Content contract — deterministic brief assembler

**Files:**
- Create: `backend/app/contract/insight.py`, `backend/tests/test_contract.py`

This is the **template/fallback path** (spec §9) — no LLM. It assembles guarded `InsightUnit`s from the snapshot + derived layer into a scenario-ordered `Brief`. The LLM-phrased path is sub-project B and will reuse these structures + the guard.

- [ ] **Step 1: Write the failing test `tests/test_contract.py`**

```python
from datetime import date

from app.contract.insight import build_brief
from app.guard import unit_supported


def test_build_brief_is_grounded_and_scenario_aware(repo, calpers):
    brief = build_brief(calpers, repo, date(2026, 6, 4))
    assert brief.client_id == "CALPERS"
    assert brief.scenario == "portfolio_review"
    assert brief.bluf                                   # non-empty bottom line
    # core sections present
    assert {"risks", "the_room", "portfolio"} <= set(brief.sections)
    # every emitted insight unit passes the guard (numbers trace to evidence)
    all_units = [u for units in brief.sections.values() for u in units]
    assert all_units and all(unit_supported(u) for u in all_units)
    # the room reflects the attending seats (2 seats -> 2 people units)
    assert len(brief.sections["the_room"]) == 2
    # portfolio cites the mandate's net excess (62) and fee (38)
    port_text = " ".join(u.insight + u.why_now for u in brief.sections["portfolio"])
    assert "62" in port_text and "38" in port_text


def test_build_brief_meta_marks_synthetic():
    # meta should flag that the CG layer is synthetic (spec §8 labeling)
    from app.config import SNAPSHOTS_DIR
    from app.data.repository import load_repository
    r = load_repository(SNAPSHOTS_DIR)
    brief = build_brief(r.get("CALPERS"), r, date(2026, 6, 4))
    assert brief.meta.get("contains_synthetic") is True
    assert brief.meta.get("disclaimer")
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_contract.py -q`
Expected: FAIL (`ModuleNotFoundError: app.contract.insight`).

- [ ] **Step 3: Implement `app/contract/insight.py`**

```python
"""Deterministic brief assembler (spec §9): snapshot + derived layer -> ranked,
guarded InsightUnits, ordered by meeting scenario. Template/fallback path (no LLM)."""
from __future__ import annotations

from datetime import date

from app.provenance import Provenance
from app.domain.models import Brief, Evidence, InsightUnit
from app.derived.risk import compute_risk
from app.derived.cost import compute_cost_effectiveness
from app.guard import guard_units

DISCLAIMER = "AI-generated brief — always verify before the meeting. Not investment advice."

# which sections lead, per scenario (spec §9)
_SCENARIO_ORDER = {
    "portfolio_review": ["risks", "portfolio", "the_room", "next_steps"],
    "finals": ["recommendations", "the_room", "risks", "next_steps"],
    "at_risk_save": ["risks", "portfolio", "the_room", "next_steps"],
    "relationship_review": ["the_room", "portfolio", "risks", "next_steps"],
}


def _ev(text: str, kind: str, url: str | None = None) -> Evidence:
    return Evidence(text=text, provenance=Provenance(kind=kind, url=url))


def _risk_units(snap, repo, now) -> list[InsightUnit]:
    units = []
    for f in compute_risk(snap, repo, now)[:4]:
        units.append(InsightUnit(
            insight=f"{f.title}: {f.evidence}",
            why_now=f"Ranked {f.severity} risk for this meeting.",
            evidence=[_ev(f.evidence, "derived")],
            severity=f.severity, score=f.score,
            freshness="frozen"))
    return units


def _portfolio_units(snap, repo) -> list[InsightUnit]:
    ce = compute_cost_effectiveness(snap, repo)
    if not snap.mandates or ce.net_value_added_bps is None:
        return []
    m = snap.mandates[0]
    return [InsightUnit(
        insight=f"{m.strategy}: net excess {m.net_excess_bps:.0f}bps at a {m.fee_bps:.0f}bps fee.",
        why_now=ce.verdict + ".",
        evidence=[_ev(ce.evidence, "synthetic"),
                  _ev(f"Information ratio {m.information_ratio}, down-capture {m.down_capture}.",
                      "synthetic")],
        play="Lead with after-fee value." , freshness="frozen")]


def _room_units(snap) -> list[InsightUnit]:
    seats = {s.id: s for s in snap.seats}
    units = []
    upcoming = snap.meetings[0] if snap.meetings else None
    seat_ids = upcoming.seat_ids if upcoming else list(seats)
    people_by_seat = {p.seat_id: p for p in snap.people}
    for sid in seat_ids:
        seat = seats.get(sid)
        if not seat:
            continue
        person = people_by_seat.get(sid)
        who = f"{person.name} — {seat.title}" if person else seat.title
        priorities = ", ".join(seat.priorities) or "priorities not on record"
        units.append(InsightUnit(
            insight=f"{who}: decides {seat.decides or 'n/a'}.",
            why_now=f"Cares about {priorities}.",
            evidence=[_ev(f"{seat.title} priorities: {priorities}.", seat.provenance.kind,
                          seat.provenance.url)],
            play="Engage on what this seat controls.", freshness="frozen"))
    return units


def _next_step_units(snap) -> list[InsightUnit]:
    items = [(i, ai) for i in snap.interactions for ai in i.open_action_items]
    units = []
    for i, ai in items:
        units.append(InsightUnit(
            insight=f"Close prior commitment: {ai}.",
            why_now="Open action item from the last interaction.",
            evidence=[_ev(ai, "synthetic")], freshness="frozen"))
    return units


def build_brief(snap, repo, now: date) -> Brief:
    upcoming = snap.meetings[0] if snap.meetings else None
    scenario = upcoming.scenario if upcoming else "relationship_review"

    sections = {
        "risks": guard_units(_risk_units(snap, repo, now)),
        "portfolio": guard_units(_portfolio_units(snap, repo)),
        "the_room": guard_units(_room_units(snap)),
        "next_steps": guard_units(_next_step_units(snap)),
    }

    top_risk = sections["risks"][0].insight if sections["risks"] else ""
    objective = (upcoming.objective if upcoming else None) or f"Relationship review — {snap.institution.name}"
    bluf = f"{objective}. Top risk — {top_risk}" if top_risk else objective

    ordered = {k: sections[k] for k in _SCENARIO_ORDER.get(scenario, list(sections)) if sections.get(k)}

    return Brief(
        client_id=snap.client_id, scenario=scenario, bluf=bluf, sections=ordered,
        meta={"generated_at": now.isoformat(), "contains_synthetic": True,
              "disclaimer": DISCLAIMER, "grounded_in": ["snapshot", "derived"]},
    )
```

- [ ] **Step 4: Run, expect PASS**

Run: `.venv/bin/python -m pytest tests/test_contract.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (Tasks 1–8).

- [ ] **Step 6: Commit**

```bash
git add app/contract/insight.py tests/test_contract.py
git commit -m "feat(v2): deterministic insight-unit brief assembler (template path)"
```

---

## Self-review (run after completing all tasks)

- [ ] **Spec coverage:** model (§5) → Tasks 1–2; grounding/snapshot corpus (§4) → Task 2; derived risk/peer/cost/delta (§5⑥, §6G) → Tasks 4–6; provenance + guard (§8) → Tasks 1, 7; content contract (§9) → Task 8. **Deferred (own plans):** ingestion pipeline (§4, A2); eval framework (§10, A3); the broader ODD operational-risk layer + PM-bio/firm-governance entities (§6 E/F — modeled & ingested in A2); generation/agent/API/UI (B/C/D).
- [ ] **Full suite green:** `.venv/bin/python -m pytest -q`.
- [ ] **No stray V1 imports:** `grep -rn "app.risk\|app.generation\|app.api\|app.agent\|loader" app tests` returns nothing.

## What A1 delivers

A pure, fully-tested data core: typed, provenance-tagged models; a committed CalPERS snapshot; a repository; a deterministic derived layer (risk, peers, cost-effectiveness, deltas); a groundedness guard; and a scenario-ordered, guarded brief assembler — runnable and testable with zero LLM/network. This is the foundation the ingestion pipeline (A2), eval harness (A3), and sub-projects B (generation/agent), C (API), and D (UI) build on.
