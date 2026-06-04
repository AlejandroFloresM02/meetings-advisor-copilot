# Pre-Meeting Brief Copilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI backend that turns the mock Capital Group CRM into a grounded pre-meeting brief copilot — served both as a chat agent (`POST /api/chat`, what the existing `UI/` calls) and as structured REST endpoints, with deterministic risk math, an LLM that only rephrases (never invents) facts, and a fact-check guard.

**Architecture:** A shared engine (grounding store → risk math → LLM phrasing → guard) is consumed by two surfaces: an OpenRouter ReAct agent's tools, and REST endpoints. Synthetic prior-meeting history is generated **offline** by a local Ollama model and frozen as committed fixtures. Runtime LLM = OpenRouter only; offline generation = Ollama only.

**Tech Stack:** Python 3.12, FastAPI + uvicorn, pydantic v2, pandas + openpyxl, LangChain (`langchain`, `langchain-openrouter`, `langchain-ollama`), pytest. Spec: `docs/superpowers/specs/2026-06-04-pre-meeting-brief-copilot-design.md`.

---

## How to build this in parallel

After **Phase 0** (one owner, ~30 min), **Track A** and **Track B** are independent and run concurrently. The only cross-track contract is the `MeetingRecord` model (fixed in Phase 0) and the fixtures (Track B → Track A), bridged by a Phase 0 **sample fixture** so Track A never blocks on Track B.

- **Phase 0 — Shared foundation:** Tasks 0.1–0.5
- **Track A — Runtime main agent (OpenRouter) + REST:** Tasks A1–A8
- **Track B — Offline transcript generation (Ollama):** Tasks B1–B3
- **Integration:** Task I1

A minimal working `POST /api/chat` (no grounded tools yet) **already exists** in `backend/app/main.py` and `backend/requirements.txt` — so the UI can light up immediately. Track A Task A7 supersedes that file with the modular, grounded version.

## File structure & canonical signatures

All paths are under `backend/`. Run all commands **from `backend/`** with the venv python (`.\.venv\Scripts\python.exe`).

```
backend/
  requirements.txt                 # EXISTS
  pyproject.toml                   # pytest config (pythonpath=".")
  app/
    __init__.py                    # EXISTS (empty)
    main.py                        # EXISTS (minimal); Task A7 rewrites it
    config.py                      # 0.2
    domain/models.py               # 0.3
    data/loader.py                 # 0.4
    data/repository.py             # 0.4
    risk/peers.py                  # A2
    risk/engine.py                 # A2
    generation/guard.py            # A3
    generation/prompts.py          # A4
    generation/brief.py            # A4
    generation/participant.py      # A5
    generation/meeting_prompts.py  # B2
    llm/base.py                    # A1
    llm/openrouter_client.py       # A1
    llm/ollama_client.py           # B1
    agent/tools.py                 # A6
    agent/runtime.py               # A6
    api/routes.py                  # A7
    api/chat.py                    # A7
  scripts/generate_meetings.py     # B2
  data/generated/meetings/ACC-1002.json   # 0.5 sample; B3 overwrites + adds rest
  preview.html                     # A8
  tests/conftest.py                # A1
  tests/test_loader.py             # 0.4
  tests/test_risk.py               # A2
  tests/test_guard.py              # A3
  tests/test_brief.py              # A4
  tests/test_participant.py        # A5
  tests/test_generator.py          # B2
  tests/test_api.py                # A7 / I1
```

**Canonical signatures (use these names exactly across tasks):**

```python
# domain/models.py — entities
Account(id, name, type, region, country_state, aum_with_cg_mm: float, tier,
        client_since: int|None, primary_strategy, relationship_manager, consultant, status)
Contact(id, account_id, name, title, role, email, phone, last_contacted: date|None)
Opportunity(id, account_id, account_name, opportunity, strategy, mandate_size_mm: float,
            stage, probability: float, weighted_mm: float|None, expected_close: date|None, owner)
Activity(id, account_id, account_name, date: date|None, contact, type, subject, owner, next_step)
Decision(text, by=None); ActionItem(text, owner=None, status="open"); TranscriptTurn(speaker, text)
MeetingRecord(id, date: date, type, title, participants: list[str], summary,
              decisions: list[Decision]=[], action_items: list[ActionItem]=[],
              participant_interests: dict[str,list[str]]={}, transcript_excerpt: list[TranscriptTurn]=[],
              source_activity: str|None=None, synthetic: bool=True)
# domain/models.py — outputs
RiskComponent(key, title, score: float, severity, evidence, sources: list[str])
RiskResult(overall: float, severity, components: list[RiskComponent])
RiskFlag(id, title, severity, score: float, evidence, explanation: str|None, sources: list[str])
TalkingPoint(text, sources: list[str])
AccountBrief(account: dict, meeting: dict, headline, risk_flags: list[RiskFlag],
             talking_points: list[TalkingPoint], since_last_meeting: dict|None,
             suggested_next_steps: list[str], meta: dict)
ParticipantCard(contact: dict, relationship: dict, interests: list[str],
                prior_decisions: list[dict], meeting_relevance, talking_point, sources: list[str])

# data/repository.py
load_repository(xlsx_path: Path, meetings_dir: Path) -> Repository
Repository.get_account(id) -> Account|None
Repository.list_accounts() -> list[Account]
Repository.contacts_for_account(id) -> list[Contact]
Repository.pipeline_for_account(id) -> list[Opportunity]
Repository.activities_for_account(id) -> list[Activity]
Repository.get_contact(id) -> Contact|None
Repository.meetings_for_account(id) -> list[MeetingRecord]
Repository.get_meeting(meeting_id) -> MeetingRecord|None
Repository.find_account(query: str) -> Account|None
Repository.find_contact(query: str) -> Contact|None

# risk/engine.py
compute_risk(repo: Repository, account_id: str, now: date) -> RiskResult
# generation/guard.py
extract_numbers(text: str) -> set[str]
statement_supported(text, sources, valid_sources: set[str], context_numbers: set[str]) -> bool
guard_statements(statements: list[dict], valid_sources, context_numbers) -> list[dict]
# llm/base.py
LLMClient.generate_json(system: str, user: str) -> dict
# generation/brief.py / participant.py
build_account_brief(repo, account_id: str, llm: LLMClient, now: date) -> AccountBrief
build_participant_card(repo, contact_id: str, account_id: str, llm: LLMClient, now: date) -> ParticipantCard
```

---

# Phase 0 — Shared foundation

### Task 0.1: Scaffold, deps, pytest config

**Files:**
- Exists: `backend/requirements.txt`
- Create: `backend/pyproject.toml`, `backend/tests/__init__.py` (empty)

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create venv and install (from `backend/`)**

Run:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: installs complete; `langchain`, `fastapi`, `pandas`, `openpyxl`, `langchain-ollama`, `pytest` present. (Behind the corporate proxy, pip may need `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.)

- [ ] **Step 3: Verify pytest runs (no tests yet is fine)**

Run: `.\.venv\Scripts\python.exe -m pytest`
Expected: "no tests ran" (exit 5) — confirms config loads.

- [ ] **Step 4: Commit**

```powershell
git add backend/pyproject.toml backend/tests/__init__.py backend/requirements.txt
git commit -m "chore: backend pytest config + deps"
```

### Task 0.2: Config

**Files:** Create `backend/app/config.py`

- [ ] **Step 1: Implement**

```python
"""Central config. Resolves paths and reads env (with safe defaults)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Reuse the teammate's key file; allow a backend-local override.
load_dotenv(REPO_ROOT / "OpenRouter_Agent" / ".env")
load_dotenv(BACKEND_ROOT / ".env")

CRM_XLSX_PATH = Path(os.getenv("CRM_XLSX_PATH", REPO_ROOT / "Capital_Group_CRM_mock.xlsx"))
MEETINGS_DIR = Path(os.getenv("MEETINGS_DIR", BACKEND_ROOT / "data" / "generated" / "meetings"))

def _now() -> date:
    raw = os.getenv("NOW_DATE", "2026-06-04")
    y, m, d = (int(x) for x in raw.split("-"))
    return date(y, m, d)

NOW: date = _now()

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "poolside/laguna-m.1:free")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_MODEL_FALLBACK = "qwen2.5-coder:7b"
PREWARM = os.getenv("PREWARM", "0") == "1"

RISK_WEIGHTS = {
    "coverage": 0.18, "recency": 0.14, "status": 0.16, "aum_vs_peers": 0.12,
    "pipeline": 0.16, "loss": 0.08, "consultant": 0.06, "open_actions": 0.10,
}
```

- [ ] **Step 2: Verify import**

Run: `.\.venv\Scripts\python.exe -c "from app.config import NOW, CRM_XLSX_PATH; print(NOW, CRM_XLSX_PATH.exists())"`
Expected: `2026-06-04 True`

- [ ] **Step 3: Commit**

```powershell
git add backend/app/config.py
git commit -m "feat: backend config + path/env resolution"
```

### Task 0.3: Domain models

**Files:** Create `backend/app/domain/__init__.py` (empty), `backend/app/domain/models.py`

- [ ] **Step 1: Implement `models.py`**

```python
"""Pydantic v2 models: CRM entities, meeting records, and API outputs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Account(BaseModel):
    id: str
    name: str
    type: str
    region: Optional[str] = None
    country_state: Optional[str] = None
    aum_with_cg_mm: float = 0.0
    tier: Optional[str] = None
    client_since: Optional[int] = None
    primary_strategy: Optional[str] = None
    relationship_manager: Optional[str] = None
    consultant: Optional[str] = None
    status: Optional[str] = None


class Contact(BaseModel):
    id: str
    account_id: str
    name: str
    title: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    last_contacted: Optional[date] = None


class Opportunity(BaseModel):
    id: str
    account_id: Optional[str] = None
    account_name: str
    opportunity: Optional[str] = None
    strategy: Optional[str] = None
    mandate_size_mm: float = 0.0
    stage: Optional[str] = None
    probability: float = 0.0
    weighted_mm: Optional[float] = None
    expected_close: Optional[date] = None
    owner: Optional[str] = None


class Activity(BaseModel):
    id: str
    account_id: Optional[str] = None
    account_name: str
    date: Optional[date] = None
    contact: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    owner: Optional[str] = None
    next_step: Optional[str] = None


class Decision(BaseModel):
    text: str
    by: Optional[str] = None


class ActionItem(BaseModel):
    text: str
    owner: Optional[str] = None
    status: str = "open"


class TranscriptTurn(BaseModel):
    speaker: str
    text: str


class MeetingRecord(BaseModel):
    id: str
    date: date
    type: Optional[str] = None
    title: str
    participants: list[str] = Field(default_factory=list)
    summary: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    participant_interests: dict[str, list[str]] = Field(default_factory=dict)
    transcript_excerpt: list[TranscriptTurn] = Field(default_factory=list)
    source_activity: Optional[str] = None
    synthetic: bool = True


class RiskComponent(BaseModel):
    key: str
    title: str
    score: float
    severity: str
    evidence: str
    sources: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    overall: float
    severity: str
    components: list[RiskComponent]


class RiskFlag(BaseModel):
    id: str
    title: str
    severity: str
    score: float
    evidence: str
    explanation: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class TalkingPoint(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)


class AccountBrief(BaseModel):
    account: dict
    meeting: dict
    headline: str
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    talking_points: list[TalkingPoint] = Field(default_factory=list)
    since_last_meeting: Optional[dict] = None
    suggested_next_steps: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class ParticipantCard(BaseModel):
    contact: dict
    relationship: dict
    interests: list[str] = Field(default_factory=list)
    prior_decisions: list[dict] = Field(default_factory=list)
    meeting_relevance: str = ""
    talking_point: str = ""
    sources: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Verify import**

Run: `.\.venv\Scripts\python.exe -c "from app.domain.models import MeetingRecord; print(MeetingRecord(id='M',date='2026-01-01',title='t').model_dump()['synthetic'])"`
Expected: `True`

- [ ] **Step 3: Commit**

```powershell
git add backend/app/domain/
git commit -m "feat: domain models (entities, meetings, brief, participant)"
```

### Task 0.4: Loader + repository (tested against the real xlsx)

**Files:** Create `backend/app/data/__init__.py` (empty), `backend/app/data/loader.py`, `backend/app/data/repository.py`, `backend/tests/test_loader.py`

- [ ] **Step 1: Write the failing test `tests/test_loader.py`**

```python
from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository


def test_calderon_loads_with_links():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    acc = repo.get_account("ACC-1002")
    assert acc is not None
    assert "Calderon" in acc.name
    assert acc.status == "Prospect"
    assert acc.aum_with_cg_mm == 0.0
    # Pipeline & Activities link by Account Name -> Account ID
    assert len(repo.pipeline_for_account("ACC-1002")) == 2
    assert len(repo.contacts_for_account("ACC-1002")) == 3
    assert len(repo.activities_for_account("ACC-1002")) >= 1
    # The trailing totals row must be dropped
    assert all(a.id for a in repo.list_accounts())
    assert len(repo.list_accounts()) == 25


def test_find_helpers():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    assert repo.find_account("calderon").id == "ACC-1002"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_loader.py -q`
Expected: FAIL (`ModuleNotFoundError: app.data.repository`).

- [ ] **Step 3: Implement `loader.py`**

```python
"""Read Capital_Group_CRM_mock.xlsx into domain models. Pipeline & Activities
carry only Account Name, so we resolve Account ID via a name->id map."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from app.domain.models import Account, Activity, Contact, MeetingRecord, Opportunity


def _s(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def _f(v) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _d(v) -> Optional[date]:
    ts = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _year(v) -> Optional[int]:
    f = _f(v)
    return int(f) if f else None


def load_accounts(xlsx: Path) -> list[Account]:
    df = pd.read_excel(xlsx, sheet_name="Accounts")
    out = []
    for _, r in df.iterrows():
        aid = _s(r.get("Account ID"))
        if not aid:  # drop the trailing totals row
            continue
        out.append(Account(
            id=aid, name=_s(r.get("Account Name")) or aid, type=_s(r.get("Type")) or "",
            region=_s(r.get("Region")), country_state=_s(r.get("Country/State")),
            aum_with_cg_mm=_f(r.get("AUM with CG ($mm)")), tier=_s(r.get("Tier")),
            client_since=_year(r.get("Client Since")), primary_strategy=_s(r.get("Primary Strategy")),
            relationship_manager=_s(r.get("Relationship Mgr")), consultant=_s(r.get("Consultant")),
            status=_s(r.get("Status")),
        ))
    return out


def load_contacts(xlsx: Path) -> list[Contact]:
    df = pd.read_excel(xlsx, sheet_name="Contacts")
    out = []
    for _, r in df.iterrows():
        cid = _s(r.get("Contact ID"))
        if not cid:
            continue
        name = " ".join(x for x in [_s(r.get("First Name")), _s(r.get("Last Name"))] if x)
        out.append(Contact(
            id=cid, account_id=_s(r.get("Account ID")) or "", name=name or cid,
            title=_s(r.get("Title")), role=_s(r.get("Role")), email=_s(r.get("Email")),
            phone=_s(r.get("Phone")), last_contacted=_d(r.get("Last Contacted")),
        ))
    return out


def load_pipeline(xlsx: Path, name_to_id: dict[str, str]) -> list[Opportunity]:
    df = pd.read_excel(xlsx, sheet_name="Pipeline")
    out = []
    for _, r in df.iterrows():
        oid = _s(r.get("Opportunity ID"))
        if not oid:
            continue
        aname = _s(r.get("Account Name")) or ""
        out.append(Opportunity(
            id=oid, account_id=name_to_id.get(aname), account_name=aname,
            opportunity=_s(r.get("Opportunity")), strategy=_s(r.get("Strategy")),
            mandate_size_mm=_f(r.get("Mandate Size ($mm)")), stage=_s(r.get("Stage")),
            probability=_f(r.get("Probability")), weighted_mm=_f(r.get("Weighted ($mm)")),
            expected_close=_d(r.get("Expected Close")), owner=_s(r.get("Owner")),
        ))
    return out


def load_activities(xlsx: Path, name_to_id: dict[str, str]) -> list[Activity]:
    df = pd.read_excel(xlsx, sheet_name="Activities")
    out = []
    for _, r in df.iterrows():
        aid = _s(r.get("Activity ID"))
        if not aid:
            continue
        aname = _s(r.get("Account Name")) or ""
        out.append(Activity(
            id=aid, account_id=name_to_id.get(aname), account_name=aname,
            date=_d(r.get("Date")), contact=_s(r.get("Contact")), type=_s(r.get("Type")),
            subject=_s(r.get("Subject")), owner=_s(r.get("Owner")), next_step=_s(r.get("Next Step")),
        ))
    return out


def load_meetings(meetings_dir: Path) -> dict[str, list[MeetingRecord]]:
    out: dict[str, list[MeetingRecord]] = {}
    if not meetings_dir.exists():
        return out
    for fp in sorted(meetings_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        acc_id = data.get("account_id") or fp.stem
        out[acc_id] = [MeetingRecord.model_validate(m) for m in data.get("meetings", [])]
    return out
```

- [ ] **Step 4: Implement `repository.py`**

```python
"""In-memory repository over the loaded CRM + meeting fixtures."""
from __future__ import annotations

from pathlib import Path

from app.data import loader
from app.domain.models import Account, Activity, Contact, MeetingRecord, Opportunity


class Repository:
    def __init__(self, accounts, contacts, opportunities, activities, meetings):
        self.accounts: dict[str, Account] = {a.id: a for a in accounts}
        self.contacts: dict[str, Contact] = {c.id: c for c in contacts}
        self.opportunities: list[Opportunity] = list(opportunities)
        self.activities: list[Activity] = list(activities)
        self.meetings: dict[str, list[MeetingRecord]] = dict(meetings)
        self._meeting_index: dict[str, MeetingRecord] = {
            m.id: m for ms in self.meetings.values() for m in ms
        }

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def list_accounts(self) -> list[Account]:
        return list(self.accounts.values())

    def contacts_for_account(self, account_id: str) -> list[Contact]:
        return [c for c in self.contacts.values() if c.account_id == account_id]

    def get_contact(self, contact_id: str) -> Contact | None:
        return self.contacts.get(contact_id)

    def pipeline_for_account(self, account_id: str) -> list[Opportunity]:
        return [o for o in self.opportunities if o.account_id == account_id]

    def activities_for_account(self, account_id: str) -> list[Activity]:
        return [a for a in self.activities if a.account_id == account_id]

    def meetings_for_account(self, account_id: str) -> list[MeetingRecord]:
        return self.meetings.get(account_id, [])

    def get_meeting(self, meeting_id: str) -> MeetingRecord | None:
        return self._meeting_index.get(meeting_id)

    def find_account(self, query: str) -> Account | None:
        q = query.strip().lower()
        if q.upper() in self.accounts:
            return self.accounts[q.upper()]
        for a in self.accounts.values():
            if q in a.name.lower():
                return a
        return None

    def find_contact(self, query: str) -> Contact | None:
        q = query.strip().lower()
        if q.upper() in self.contacts:
            return self.contacts[q.upper()]
        for c in self.contacts.values():
            if q in c.name.lower():
                return c
        return None


def load_repository(xlsx_path: Path, meetings_dir: Path) -> Repository:
    accounts = loader.load_accounts(xlsx_path)
    name_to_id = {a.name: a.id for a in accounts}
    contacts = loader.load_contacts(xlsx_path)
    opportunities = loader.load_pipeline(xlsx_path, name_to_id)
    activities = loader.load_activities(xlsx_path, name_to_id)
    meetings = loader.load_meetings(meetings_dir)
    return Repository(accounts, contacts, opportunities, activities, meetings)
```

- [ ] **Step 5: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_loader.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```powershell
git add backend/app/data/ backend/tests/test_loader.py
git commit -m "feat: xlsx loader + in-memory repository with name->id linking"
```

### Task 0.5: Sample meeting fixture + repository wiring

**Files:** Create `backend/data/generated/meetings/ACC-1002.json`

- [ ] **Step 1: Hand-author the sample fixture (real IDs from the dataset)**

```json
{
  "account_id": "ACC-1002",
  "meetings": [
    {
      "id": "MTG-1002-01",
      "date": "2026-05-07",
      "type": "Call",
      "title": "Performance check-in call",
      "participants": ["CON-2004", "CON-2005"],
      "summary": "Quarterly check-in on the Bond Fund of America due-diligence track. Patricia Schmidt reiterated the board's fee sensitivity following their last manager search; Lisa Schmidt confirmed scheduling for the finals window.",
      "decisions": [
        { "text": "Proceed to due diligence on the $600.5mm Bond Fund of America mandate", "by": "CON-2004" }
      ],
      "action_items": [
        { "text": "Share peer benchmarking data", "owner": "Diane Okafor", "status": "open" },
        { "text": "Provide sub-$500mm breakpoint fee schedule to Mercer", "owner": "Diane Okafor", "status": "open" }
      ],
      "participant_interests": {
        "CON-2004": ["fee transparency", "downside protection"],
        "CON-2005": ["scheduling/onboarding readiness"]
      },
      "transcript_excerpt": [
        { "speaker": "Patricia Schmidt", "text": "The board is still sensitive on fees after the last search." },
        { "speaker": "Diane Okafor", "text": "Understood — I'll get Mercer the breakpoint schedule this week." }
      ],
      "source_activity": "ACT-4004",
      "synthetic": true
    }
  ]
}
```

- [ ] **Step 2: Verify it loads via the repository**

Run: `.\.venv\Scripts\python.exe -c "from app.config import *; from app.data.repository import load_repository; r=load_repository(CRM_XLSX_PATH, MEETINGS_DIR); print([m.id for m in r.meetings_for_account('ACC-1002')])"`
Expected: `['MTG-1002-01']`

- [ ] **Step 3: Commit**

```powershell
git add backend/data/generated/meetings/ACC-1002.json
git commit -m "feat: sample ACC-1002 meeting fixture (unblocks Track A)"
```

> **Phase 0 complete. Track A and Track B can now proceed in parallel.**

---

# Track A — Runtime main agent (OpenRouter) + REST

### Task A1: LLM base + OpenRouter client + test StubLLM

**Files:** Create `backend/app/llm/__init__.py` (empty), `backend/app/llm/base.py`, `backend/app/llm/openrouter_client.py`, `backend/tests/conftest.py`

- [ ] **Step 1: Implement `llm/base.py`**

```python
"""Shared LLM interface used by generation + the agent's tools."""
from __future__ import annotations

import json
import re
from typing import Protocol


class LLMClient(Protocol):
    def generate_json(self, system: str, user: str) -> dict:
        """Return a parsed JSON object from the model (or {} on failure)."""
        ...


def parse_json_object(text: str) -> dict:
    """Best-effort: parse the first {...} block out of a model response."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return {}
```

- [ ] **Step 2: Implement `llm/openrouter_client.py`**

```python
"""Runtime LLM (OpenRouter only). Exposes the TLS-bypass chat model for the
ReAct agent AND a generate_json client for generation/tools."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

from app import config
from app.llm.base import parse_json_object


class CertificateBypassingChatOpenRouter(ChatOpenRouter):
    """ChatOpenRouter that disables TLS verification (corporate proxy)."""

    def _build_client(self) -> Any:
        import httpx
        import openrouter
        from openrouter.utils import BackoffStrategy, RetryConfig

        kw: dict[str, Any] = {"api_key": self.openrouter_api_key.get_secret_value()}
        if self.openrouter_api_base:
            kw["server_url"] = self.openrouter_api_base
        headers = {"X-Title": self.app_title} if self.app_title else {}
        kw["client"] = httpx.Client(headers=headers, follow_redirects=True, verify=False)
        kw["async_client"] = httpx.AsyncClient(headers=headers, follow_redirects=True, verify=False)
        if self.request_timeout is not None:
            kw["timeout_ms"] = self.request_timeout
        if self.max_retries > 0:
            kw["retry_config"] = RetryConfig(
                strategy="backoff",
                backoff=BackoffStrategy(initial_interval=500, max_interval=60000,
                                        exponent=1.5, max_elapsed_time=self.max_retries * 150_000),
                retry_connection_errors=True,
            )
        return openrouter.OpenRouter(**kw)


def build_chat_model() -> CertificateBypassingChatOpenRouter:
    return CertificateBypassingChatOpenRouter(
        model=config.OPENROUTER_MODEL, temperature=0.3, max_tokens=1024,
        max_retries=2, app_title="Sage Brief Copilot",
    )


class OpenRouterClient:
    """generate_json over the TLS-bypass chat model."""

    def __init__(self, model: CertificateBypassingChatOpenRouter | None = None):
        self._model = model or build_chat_model()

    def generate_json(self, system: str, user: str) -> dict:
        try:
            resp = self._model.invoke([
                SystemMessage(content=system + " Respond with a single valid JSON object and nothing else."),
                HumanMessage(content=user),
            ])
            return parse_json_object(getattr(resp, "content", "") or "")
        except Exception:
            return {}
```

- [ ] **Step 3: Implement `tests/conftest.py` (shared fixtures + StubLLM)**

```python
import pytest

from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository


class StubLLM:
    """Deterministic fake LLMClient. Set `.payload` to the dict to return."""
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.calls = []

    def generate_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        return self.payload


@pytest.fixture
def repo():
    return load_repository(CRM_XLSX_PATH, MEETINGS_DIR)


@pytest.fixture
def stub_llm():
    return StubLLM()
```

- [ ] **Step 4: Verify import (no network call)**

Run: `.\.venv\Scripts\python.exe -c "from app.llm.base import parse_json_object; print(parse_json_object('noise {\"a\": 1} tail'))"`
Expected: `{'a': 1}`

- [ ] **Step 5: Commit**

```powershell
git add backend/app/llm/base.py backend/app/llm/openrouter_client.py backend/app/llm/__init__.py backend/tests/conftest.py
git commit -m "feat: LLM interface + OpenRouter TLS-bypass client + test StubLLM"
```

### Task A2: Risk engine

**Files:** Create `backend/app/risk/__init__.py` (empty), `backend/app/risk/peers.py`, `backend/app/risk/engine.py`, `backend/tests/test_risk.py`

- [ ] **Step 1: Write the failing test `tests/test_risk.py`**

```python
from datetime import date

from app.risk.engine import compute_risk, severity_band


def test_severity_bands():
    assert severity_band(0.9) == "high"
    assert severity_band(0.5) == "medium"
    assert severity_band(0.1) == "low"


def test_calderon_flags_no_decision_maker_and_prospect(repo):
    res = compute_risk(repo, "ACC-1002", date(2026, 6, 4))
    keys = {c.key for c in res.components}
    assert {"coverage", "status", "pipeline", "consultant"} <= keys
    coverage = next(c for c in res.components if c.key == "coverage")
    assert coverage.severity == "high"        # no Decision Maker mapped
    assert "Decision Maker" in coverage.evidence
    assert 0.0 <= res.overall <= 1.0


def test_at_risk_account_scores_status_high(repo):
    res = compute_risk(repo, "ACC-1017", date(2026, 6, 4))  # Stonebridge, At Risk
    status = next(c for c in res.components if c.key == "status")
    assert status.severity == "high"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_risk.py -q`
Expected: FAIL (`ModuleNotFoundError: app.risk.engine`).

- [ ] **Step 3: Implement `risk/peers.py`**

```python
from __future__ import annotations


def percentile_rank(values: list[float], value: float) -> float:
    """Fraction of `values` <= `value` (0..1). Empty -> 0.5."""
    if not values:
        return 0.5
    return sum(1 for v in values if v <= value) / len(values)
```

- [ ] **Step 4: Implement `risk/engine.py`**

```python
"""Deterministic risk math. Each component -> (score 0..1, evidence, sources)."""
from __future__ import annotations

from datetime import date

from app.config import RISK_WEIGHTS
from app.domain.models import RiskComponent, RiskResult
from app.risk.peers import percentile_rank


def severity_band(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def _comp(key, title, score, evidence, sources) -> RiskComponent:
    score = max(0.0, min(1.0, score))
    return RiskComponent(key=key, title=title, score=score,
                         severity=severity_band(score), evidence=evidence, sources=sources)


def compute_risk(repo, account_id: str, now: date) -> RiskResult:
    acc = repo.get_account(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    meetings = repo.meetings_for_account(account_id)
    comps: list[RiskComponent] = []

    # coverage
    roles = [c.role for c in contacts]
    has_dm = any(r == "Decision Maker" for r in roles)
    n = len(contacts)
    if n == 0:
        comps.append(_comp("coverage", "Stakeholder coverage", 0.7, "No contacts mapped.", []))
    else:
        breakdown = ", ".join(f"{roles.count(r)} {r}" for r in sorted(set(roles)) if r)
        score = 0.82 if not has_dm else 0.25
        comps.append(_comp("coverage", "Stakeholder coverage", score,
                           f"{n} contacts: {breakdown}; {'no Decision Maker mapped' if not has_dm else 'Decision Maker mapped'}.",
                           [c.id for c in contacts]))

    # recency
    dated = [c for c in contacts if c.last_contacted]
    if dated:
        latest = max(dated, key=lambda c: c.last_contacted)
        days = (now - latest.last_contacted).days
        score = min(1.0, max(0.0, (days - 30) / 150))
        comps.append(_comp("recency", "Relationship recency", score,
                           f"Most recent contact {days} days ago ({latest.last_contacted.isoformat()}).",
                           [latest.id]))
    else:
        comps.append(_comp("recency", "Relationship recency", 0.6, "No contact dates on record.", []))

    # status
    smap = {"At Risk": 0.9, "Prospect": 0.5, "Active": 0.2}
    s = acc.status or ""
    comps.append(_comp("status", "Account status", smap.get(s, 0.3), f"Account status: {s or 'unknown'}.", [acc.id]))

    # aum vs peers
    if (acc.status == "Prospect") or acc.aum_with_cg_mm == 0.0:
        comps.append(_comp("aum_vs_peers", "AUM vs peers", 0.4,
                           f"${acc.aum_with_cg_mm:.0f}mm current AUM (prospect / conversion).", [acc.id]))
    else:
        peers = [a.aum_with_cg_mm for a in repo.list_accounts()
                 if a.type == acc.type and a.aum_with_cg_mm > 0 and a.id != acc.id]
        pct = percentile_rank(peers, acc.aum_with_cg_mm)
        comps.append(_comp("aum_vs_peers", "AUM vs peers", 1.0 - pct,
                           f"${acc.aum_with_cg_mm:.0f}mm = {pct:.0%} percentile among {acc.type} peers.", [acc.id]))

    # pipeline
    open_opps = [o for o in opps if (o.stage or "") not in ("Won", "Lost")]
    if not open_opps:
        comps.append(_comp("pipeline", "Pipeline dynamics", 0.1, "No open pipeline.", []))
    else:
        weighted = sum(o.mandate_size_mm * o.probability for o in open_opps)
        closes = [(o.expected_close - now).days for o in open_opps if o.expected_close]
        nearest = min(closes) if closes else None
        score = 0.8 if (nearest is not None and nearest < 60) else 0.5 if (nearest is not None and nearest < 120) else 0.3
        near_txt = f"nearest close in {nearest}d" if nearest is not None else "no close dates"
        comps.append(_comp("pipeline", "Pipeline dynamics", score,
                           f"{len(open_opps)} open opps, ${weighted:.0f}mm prob-weighted; {near_txt}.",
                           [o.id for o in open_opps]))

    # loss history (trailing 12 months)
    lost = [o for o in opps if (o.stage == "Lost") and o.expected_close and (now - o.expected_close).days <= 365]
    comps.append(_comp("loss", "Loss history", 0.6 if lost else 0.1,
                       f"{len(lost)} lost opportunity(ies) in the trailing 12 months.", [o.id for o in lost]))

    # consultant influence
    ext = bool(acc.consultant) and acc.consultant != "In-house"
    comps.append(_comp("consultant", "Consultant influence", 0.5 if ext else 0.15,
                       f"Consultant: {acc.consultant or 'unknown'}{' (external influence)' if ext else ''}.", [acc.id]))

    # open action items from prior meetings
    open_items = [(m.id, ai) for m in meetings for ai in m.action_items if ai.status == "open"]
    if open_items:
        comps.append(_comp("open_actions", "Open action items", min(1.0, 0.3 + 0.2 * len(open_items)),
                           f"{len(open_items)} open action item(s) from prior meetings.",
                           sorted({mid for mid, _ in open_items})))
    else:
        comps.append(_comp("open_actions", "Open action items", 0.1, "No open action items.", []))

    total_w = sum(RISK_WEIGHTS.get(c.key, 0) for c in comps) or 1.0
    overall = sum(RISK_WEIGHTS.get(c.key, 0) * c.score for c in comps) / total_w
    comps.sort(key=lambda c: c.score, reverse=True)
    return RiskResult(overall=overall, severity=severity_band(overall), components=comps)
```

- [ ] **Step 5: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_risk.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```powershell
git add backend/app/risk/ backend/tests/test_risk.py
git commit -m "feat: deterministic risk engine (8 components, peer-relative AUM)"
```

### Task A3: Fact-check guard

**Files:** Create `backend/app/generation/__init__.py` (empty), `backend/app/generation/guard.py`, `backend/tests/test_guard.py`

- [ ] **Step 1: Write the failing test `tests/test_guard.py`**

```python
from app.generation.guard import extract_numbers, guard_statements, statement_supported


def test_extract_numbers_strips_punctuation():
    nums = extract_numbers("~$946mm across 2 mandates at 80%")
    assert {"946", "2", "80"} <= nums


def test_unsupported_source_is_dropped():
    valid = {"OPP-3003", "CON-2004"}
    ctx = {"600"}
    assert statement_supported("Advance the $600mm mandate", ["OPP-3003"], valid, ctx)
    assert not statement_supported("Advance it", ["OPP-9999"], valid, ctx)  # bad source
    assert not statement_supported("It is worth $700mm", ["OPP-3003"], valid, ctx)  # bad number


def test_guard_filters_list():
    valid = {"OPP-3003"}
    ctx = {"600"}
    stmts = [
        {"text": "$600mm in DD", "sources": ["OPP-3003"]},
        {"text": "$700mm fabricated", "sources": ["OPP-3003"]},
    ]
    kept = guard_statements(stmts, valid, ctx)
    assert len(kept) == 1 and kept[0]["text"] == "$600mm in DD"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_guard.py -q`
Expected: FAIL (`ModuleNotFoundError: app.generation.guard`).

- [ ] **Step 3: Implement `generation/guard.py`**

```python
"""Fact-check guard: a statement survives only if every source is valid and
every number it states appears in the grounded context."""
from __future__ import annotations

import re

_NUM = re.compile(r"\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.findall(text or ""):
        out.add(m)
        if "." in m:                 # also index the integer part ("946.0" -> "946")
            out.add(m.split(".")[0])
    return out


def statement_supported(text, sources, valid_sources: set[str], context_numbers: set[str]) -> bool:
    if sources and not all(s in valid_sources for s in sources):
        return False
    nums = extract_numbers(text)
    if nums and not nums <= _expand(context_numbers):
        return False
    return True


def _expand(numbers: set[str]) -> set[str]:
    out = set(numbers)
    for n in numbers:
        if "." in n:
            out.add(n.split(".")[0])
    return out


def guard_statements(statements: list[dict], valid_sources: set[str], context_numbers: set[str]) -> list[dict]:
    kept = []
    for s in statements:
        text = (s.get("text") or "").strip()
        if text and statement_supported(text, s.get("sources", []), valid_sources, context_numbers):
            kept.append({"text": text, "sources": s.get("sources", [])})
    return kept
```

- [ ] **Step 4: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_guard.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```powershell
git add backend/app/generation/guard.py backend/app/generation/__init__.py backend/tests/test_guard.py
git commit -m "feat: fact-check guard (source + number verification)"
```

### Task A4: Brief generation (prompts + builder + fallback)

**Files:** Create `backend/app/generation/prompts.py`, `backend/app/generation/brief.py`, `backend/tests/test_brief.py`

- [ ] **Step 1: Write the failing test `tests/test_brief.py`**

```python
from datetime import date

from app.generation.brief import build_account_brief


def test_brief_uses_guarded_llm_output(repo):
    from tests.conftest import StubLLM
    llm = StubLLM({
        "headline": "Two late-stage mandates in play.",
        "risk_explanations": {"coverage": "No economic buyer is mapped yet."},
        "talking_points": [
            {"text": "Advance the Bond Fund DD mandate", "sources": ["OPP-3003"]},
            {"text": "Fabricated $999mm claim", "sources": ["OPP-3003"]},  # bad number -> dropped
        ],
        "next_steps": ["Send Mercer the breakpoint schedule"],
    })
    brief = build_account_brief(repo, "ACC-1002", llm, date(2026, 6, 4))
    assert brief.headline == "Two late-stage mandates in play."
    texts = [t.text for t in brief.talking_points]
    assert "Advance the Bond Fund DD mandate" in texts
    assert all("999" not in t for t in texts)            # guard dropped the fake number
    assert any(f.id == "coverage" for f in brief.risk_flags)
    assert brief.meta["grounded_in"]


def test_brief_falls_back_when_llm_empty(repo):
    from tests.conftest import StubLLM
    brief = build_account_brief(repo, "ACC-1002", StubLLM({}), date(2026, 6, 4))
    assert brief.headline                                  # template fallback
    assert len(brief.talking_points) >= 1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_brief.py -q`
Expected: FAIL (`ModuleNotFoundError: app.generation.brief`).

- [ ] **Step 3: Implement `generation/prompts.py`**

```python
"""Prompt builders. The model receives ONLY structured facts and must cite IDs."""
from __future__ import annotations

import json

BRIEF_SYSTEM = (
    "You are a Capital Group institutional relationship-management analyst. "
    "You write pre-meeting briefs. Use ONLY the facts provided. Never invent numbers, "
    "names, dates, or claims. Every talking point and risk explanation must cite the "
    "fact id(s) it is based on, drawn from the provided 'fact_ids'. "
    "Return JSON: {\"headline\": str, \"risk_explanations\": {component_key: str}, "
    "\"talking_points\": [{\"text\": str, \"sources\": [fact_id]}], \"next_steps\": [str]}."
)

PARTICIPANT_SYSTEM = (
    "You are a Capital Group RM analyst writing a one-paragraph profile of a meeting "
    "participant. Use ONLY the facts provided; never invent. Cite fact ids. "
    "Return JSON: {\"meeting_relevance\": str, \"talking_point\": str, \"sources\": [fact_id]}."
)


def build_brief_user(facts: dict) -> str:
    return "FACTS (JSON):\n" + json.dumps(facts, indent=2, default=str)


def build_participant_user(facts: dict) -> str:
    return "FACTS (JSON):\n" + json.dumps(facts, indent=2, default=str)
```

- [ ] **Step 4: Implement `generation/brief.py`**

```python
"""Assemble facts -> LLM phrasing -> guard -> AccountBrief, with template fallback."""
from __future__ import annotations

from datetime import date

from app.domain.models import AccountBrief, RiskFlag, TalkingPoint
from app.generation.guard import extract_numbers, guard_statements, statement_supported
from app.generation.prompts import BRIEF_SYSTEM, build_brief_user
from app.risk.engine import compute_risk
from app import config


def _valid_sources(acc, contacts, opps, activities, meetings) -> set[str]:
    return ({acc.id} | {c.id for c in contacts} | {o.id for o in opps}
            | {a.id for a in activities} | {m.id for m in meetings})


def _context_numbers(acc, opps, risk) -> set[str]:
    text = " ".join(
        [c.evidence for c in risk.components]
        + [f"{acc.aum_with_cg_mm}"]
        + [f"{o.mandate_size_mm} {o.probability} {int(o.probability * 100)}" for o in opps]
    )
    return extract_numbers(text)


def _derive_meeting(acc, opps, now: date) -> dict:
    open_opps = [o for o in opps if (o.stage or "") not in ("Won", "Lost")]
    open_opps.sort(key=lambda o: o.expected_close or date.max)
    purpose = (f"Advance {open_opps[0].opportunity}" if open_opps
               else f"Relationship review — {acc.name}")
    return {"purpose": purpose, "date": now.isoformat(), "participant_count": None}


def _since_last_meeting(meetings) -> dict | None:
    if not meetings:
        return None
    last = max(meetings, key=lambda m: m.date)
    open_items = [{"text": ai.text, "sources": [last.id]} for ai in last.action_items if ai.status == "open"]
    return {"summary": last.summary, "meeting_id": last.id, "date": last.date.isoformat(),
            "open_action_items": open_items}


def _fallback_talking_points(acc, opps, meetings) -> list[TalkingPoint]:
    tps = []
    for o in opps:
        if (o.stage or "") not in ("Won", "Lost"):
            tps.append(TalkingPoint(
                text=f"Advance {o.opportunity} (${o.mandate_size_mm:.0f}mm, {o.stage}, {int(o.probability*100)}% prob).",
                sources=[o.id]))
    for m in meetings:
        for ai in m.action_items:
            if ai.status == "open":
                tps.append(TalkingPoint(text=f"Close prior commitment: {ai.text}.", sources=[m.id]))
    if not tps:
        tps.append(TalkingPoint(text=f"Reaffirm the relationship with {acc.name}.", sources=[acc.id]))
    return tps[:5]


def build_account_brief(repo, account_id: str, llm, now: date) -> AccountBrief:
    acc = repo.get_account(account_id)
    if acc is None:
        raise KeyError(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    activities = repo.activities_for_account(account_id)
    meetings = repo.meetings_for_account(account_id)
    risk = compute_risk(repo, account_id, now)

    valid = _valid_sources(acc, contacts, opps, activities, meetings)
    ctx_nums = _context_numbers(acc, opps, risk)

    facts = {
        "account": acc.model_dump(),
        "fact_ids": sorted(valid),
        "risk_components": [c.model_dump() for c in risk.components],
        "open_pipeline": [o.model_dump() for o in opps if (o.stage or "") not in ("Won", "Lost")],
        "recent_meetings": [{"id": m.id, "date": str(m.date), "summary": m.summary,
                             "decisions": [d.model_dump() for d in m.decisions],
                             "open_action_items": [ai.text for ai in m.action_items if ai.status == "open"]}
                            for m in meetings],
    }

    raw = {}
    try:
        raw = llm.generate_json(BRIEF_SYSTEM, build_brief_user(facts))
    except Exception:
        raw = {}

    tps_raw = raw.get("talking_points") if isinstance(raw.get("talking_points"), list) else []
    tps = [TalkingPoint(**s) for s in guard_statements(tps_raw, valid, ctx_nums)]
    if not tps:
        tps = _fallback_talking_points(acc, opps, meetings)

    expl = raw.get("risk_explanations") or {}
    flags = []
    for c in risk.components[:5]:
        e = expl.get(c.key) if isinstance(expl, dict) else None
        if e and not statement_supported(e, c.sources, valid, ctx_nums):
            e = None
        flags.append(RiskFlag(id=c.key, title=c.title, severity=c.severity, score=c.score,
                              evidence=c.evidence, explanation=e, sources=c.sources))

    headline = (raw.get("headline") or "").strip() or (
        f"{acc.tier or ''} {acc.status or ''} account; top risk: {risk.components[0].title.lower()}." )
    next_steps = [s for s in (raw.get("next_steps") or []) if isinstance(s, str) and s.strip()]
    if not next_steps:
        next_steps = [ai.text for m in meetings for ai in m.action_items if ai.status == "open"][:3] \
            or ["Confirm objectives and next steps with the client."]

    return AccountBrief(
        account={"id": acc.id, "name": acc.name, "type": acc.type, "tier": acc.tier,
                 "status": acc.status, "aum_with_cg_mm": acc.aum_with_cg_mm,
                 "primary_strategy": acc.primary_strategy,
                 "relationship_manager": acc.relationship_manager, "consultant": acc.consultant},
        meeting=_derive_meeting(acc, opps, now),
        headline=headline,
        risk_flags=flags,
        talking_points=tps,
        since_last_meeting=_since_last_meeting(meetings),
        suggested_next_steps=next_steps,
        meta={"generated_at": now.isoformat(), "provider": "openrouter",
              "model": config.OPENROUTER_MODEL,
              "grounded_in": ["Capital_Group_CRM_mock.xlsx", "meeting-fixtures"]},
    )
```

- [ ] **Step 5: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_brief.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```powershell
git add backend/app/generation/prompts.py backend/app/generation/brief.py backend/tests/test_brief.py
git commit -m "feat: account brief generation (guarded LLM + template fallback)"
```

### Task A5: Participant card generation

**Files:** Create `backend/app/generation/participant.py`, `backend/tests/test_participant.py`

- [ ] **Step 1: Write the failing test `tests/test_participant.py`**

```python
from datetime import date

from app.generation.participant import build_participant_card


def test_participant_card_grounded(repo):
    from tests.conftest import StubLLM
    llm = StubLLM({"meeting_relevance": "Gatekeeper controlling committee access.",
                   "talking_point": "Confirm the funding timeline.",
                   "sources": ["CON-2005"]})
    card = build_participant_card(repo, "CON-2005", "ACC-1002", llm, date(2026, 6, 4))
    assert card.contact["id"] == "CON-2005"
    assert card.contact["role"]
    assert "relationship" in card.model_dump()
    assert card.meeting_relevance


def test_participant_card_fallback(repo):
    from tests.conftest import StubLLM
    card = build_participant_card(repo, "CON-2005", "ACC-1002", StubLLM({}), date(2026, 6, 4))
    assert card.meeting_relevance        # falls back to a templated line
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_participant.py -q`
Expected: FAIL (`ModuleNotFoundError: app.generation.participant`).

- [ ] **Step 3: Implement `generation/participant.py`**

```python
"""Per-participant card: relationship facts + interests/prior decisions from
meeting fixtures, phrased by the LLM, guarded."""
from __future__ import annotations

from datetime import date

from app.domain.models import ParticipantCard
from app.generation.guard import extract_numbers, statement_supported
from app.generation.prompts import PARTICIPANT_SYSTEM, build_participant_user


def build_participant_card(repo, contact_id: str, account_id: str, llm, now: date) -> ParticipantCard:
    contact = repo.get_contact(contact_id)
    if contact is None:
        raise KeyError(contact_id)
    meetings = repo.meetings_for_account(account_id)
    activities = repo.activities_for_account(account_id)

    interests: list[str] = []
    prior_decisions: list[dict] = []
    meeting_sources: list[str] = []
    for m in meetings:
        if contact_id in m.participants:
            meeting_sources.append(m.id)
            interests.extend(m.participant_interests.get(contact_id, []))
            for d in m.decisions:
                if d.by == contact_id:
                    prior_decisions.append({"text": d.text, "meeting": m.id})
    interests = list(dict.fromkeys(interests))

    recent = [{"id": a.id, "date": str(a.date), "subject": a.subject}
              for a in activities if a.contact and contact.name and a.contact in contact.name][:3]
    days_since = (now - contact.last_contacted).days if contact.last_contacted else None

    valid = {contact_id, account_id} | {m.id for m in meetings} | {a.id for a in activities}
    ctx_nums = extract_numbers(" ".join(interests + [d["text"] for d in prior_decisions]))

    facts = {
        "contact": contact.model_dump(),
        "fact_ids": sorted(valid),
        "interests": interests,
        "prior_decisions": prior_decisions,
        "days_since_contact": days_since,
    }
    raw = {}
    try:
        raw = llm.generate_json(PARTICIPANT_SYSTEM, build_participant_user(facts))
    except Exception:
        raw = {}

    relevance = (raw.get("meeting_relevance") or "").strip()
    srcs = raw.get("sources") or [contact_id]
    if relevance and not statement_supported(relevance, srcs, valid, ctx_nums):
        relevance = ""
    if not relevance:
        relevance = f"{contact.role or 'Stakeholder'} at the account" + (
            f"; interests: {', '.join(interests)}." if interests else ".")

    talking_point = (raw.get("talking_point") or "").strip()
    if talking_point and not statement_supported(talking_point, srcs, valid, ctx_nums):
        talking_point = ""
    if not talking_point:
        talking_point = (f"Acknowledge {contact.name}'s focus on {interests[0]}." if interests
                         else f"Re-engage {contact.name} ({contact.role or 'contact'}).")

    return ParticipantCard(
        contact={"id": contact.id, "name": contact.name, "title": contact.title,
                 "role": contact.role, "account_id": contact.account_id,
                 "last_contacted": contact.last_contacted.isoformat() if contact.last_contacted else None,
                 "email": contact.email, "phone": contact.phone},
        relationship={"days_since_contact": days_since, "recent_interactions": recent},
        interests=interests,
        prior_decisions=prior_decisions,
        meeting_relevance=relevance,
        talking_point=talking_point,
        sources=sorted(set([contact_id] + meeting_sources)),
    )
```

- [ ] **Step 4: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_participant.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```powershell
git add backend/app/generation/participant.py backend/tests/test_participant.py
git commit -m "feat: participant card generation (interests + prior decisions, guarded)"
```

### Task A6: Agent tools + ReAct runtime

**Files:** Create `backend/app/agent/__init__.py` (empty), `backend/app/agent/tools.py`, `backend/app/agent/runtime.py`

- [ ] **Step 1: Implement `agent/tools.py`**

```python
"""Grounded tools for the ReAct agent. Configure once with repo + llm, then the
tools render the same builders as the REST endpoints into chat-ready markdown."""
from __future__ import annotations

from datetime import date

from langchain_core.tools import tool

from app.generation.brief import build_account_brief
from app.generation.participant import build_participant_card

_STATE: dict = {"repo": None, "llm": None, "now": None}


def configure(repo, llm, now: date) -> None:
    _STATE.update(repo=repo, llm=llm, now=now)


def _resolve_account_id(query: str) -> str | None:
    repo = _STATE["repo"]
    if repo.get_account(query):
        return query
    a = repo.find_account(query)
    return a.id if a else None


def brief_to_md(b) -> str:
    lines = [f"**{b.account['name']}** — {b.headline}", ""]
    lines.append(f"_Snapshot:_ {b.account.get('tier')} · {b.account.get('status')} · "
                 f"${b.account.get('aum_with_cg_mm'):.0f}mm AUM · consultant {b.account.get('consultant')}")
    lines.append("\n**Risk flags:**")
    for f in b.risk_flags:
        ex = f" — {f.explanation}" if f.explanation else ""
        lines.append(f"- [{f.severity.upper()}] {f.title}: {f.evidence}{ex}")
    lines.append("\n**Talking points:**")
    for t in b.talking_points:
        lines.append(f"- {t.text}")
    if b.suggested_next_steps:
        lines.append("\n**Next steps:** " + "; ".join(b.suggested_next_steps))
    return "\n".join(lines)


@tool
def get_account_brief(account: str) -> str:
    """Generate the pre-meeting brief for an account by ID (ACC-1002) or name (Calderon)."""
    aid = _resolve_account_id(account)
    if not aid:
        return f"No account found matching '{account}'."
    b = build_account_brief(_STATE["repo"], aid, _STATE["llm"], _STATE["now"])
    return brief_to_md(b)


@tool
def get_participant_card(name_or_id: str, account: str) -> str:
    """Profile a meeting participant (by contact name or ID) for a given account."""
    repo = _STATE["repo"]
    aid = _resolve_account_id(account)
    contact = repo.get_contact(name_or_id) or repo.find_contact(name_or_id)
    if not contact or not aid:
        return f"No participant '{name_or_id}' found for account '{account}'."
    c = build_participant_card(repo, contact.id, aid, _STATE["llm"], _STATE["now"])
    rel = f"last contacted {c.relationship['days_since_contact']}d ago" if c.relationship.get("days_since_contact") is not None else ""
    return (f"**{c.contact['name']}** — {c.contact['title']} ({c.contact['role']}). {rel}\n"
            f"{c.meeting_relevance}\nInterests: {', '.join(c.interests) or 'n/a'}\n"
            f"Talking point: {c.talking_point}")


@tool
def list_today_meetings() -> str:
    """List the accounts with upcoming meetings (the Today's Meetings list)."""
    repo = _STATE["repo"]
    rows = [f"- {a.id} {a.name} ({a.status}, {a.tier})" for a in repo.list_accounts()]
    return "Accounts:\n" + "\n".join(rows[:25])


@tool
def get_meeting_history(account: str) -> str:
    """Summaries of prior (synthetic) meetings for an account."""
    aid = _resolve_account_id(account)
    if not aid:
        return f"No account matching '{account}'."
    ms = _STATE["repo"].meetings_for_account(aid)
    if not ms:
        return "No prior meetings on record."
    return "\n".join(f"- {m.date} {m.title}: {m.summary}" for m in ms)


TOOLS = [get_account_brief, get_participant_card, list_today_meetings, get_meeting_history]
```

- [ ] **Step 2: Implement `agent/runtime.py`**

```python
"""Build the OpenRouter ReAct agent with grounded tools + per-thread memory."""
from __future__ import annotations

from datetime import date

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import tools as agent_tools
from app.llm.openrouter_client import build_chat_model

SYSTEM_PROMPT = (
    "You are Sage, a pre-meeting brief copilot for Capital Group institutional "
    "relationship managers. For ANY question about an account, person, meeting, or "
    "risk, you MUST call the appropriate tool and base your answer only on its output. "
    "Never invent numbers, names, or facts. Be concise and professional."
)


def build_agent(repo, llm, now: date):
    agent_tools.configure(repo, llm, now)
    model = build_chat_model()
    return create_agent(model=model, tools=agent_tools.TOOLS,
                        system_prompt=SYSTEM_PROMPT, checkpointer=InMemorySaver())
```

- [ ] **Step 3: Verify tools work offline (no agent/network — use StubLLM)**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from datetime import date; from app.config import *; from app.data.repository import load_repository; from app.agent import tools; from tests.conftest import StubLLM; r=load_repository(CRM_XLSX_PATH, MEETINGS_DIR); tools.configure(r, StubLLM({}), date(2026,6,4)); print(tools.get_account_brief.invoke({'account':'Calderon'})[:200])"
```
Expected: markdown beginning with `**State of Calderon Teachers' Retirement System...** ` (or the Calderon name) and risk flags.

- [ ] **Step 4: Commit**

```powershell
git add backend/app/agent/
git commit -m "feat: grounded ReAct agent tools + OpenRouter runtime"
```

### Task A7: REST routes + chat endpoint + app wiring

**Files:** Create `backend/app/api/__init__.py` (empty), `backend/app/api/routes.py`, `backend/app/api/chat.py`; **rewrite** `backend/app/main.py`; create `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing test `tests/test_api.py`**

```python
from fastapi.testclient import TestClient


def _client(monkeypatch):
    # Force the REST builders to use the deterministic StubLLM (no network).
    from tests.conftest import StubLLM
    import app.api.routes as routes
    monkeypatch.setattr(routes, "_make_llm", lambda: StubLLM({}))
    from app.main import app
    return TestClient(app)


def test_health(monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/api/health").json()["status"] == "ok"


def test_accounts_and_brief(monkeypatch):
    c = _client(monkeypatch)
    accts = c.get("/api/accounts").json()
    assert any(a["id"] == "ACC-1002" for a in accts)
    brief = c.get("/api/accounts/ACC-1002/brief").json()
    assert brief["headline"]
    assert any(f["id"] == "coverage" for f in brief["risk_flags"])


def test_participant(monkeypatch):
    c = _client(monkeypatch)
    card = c.get("/api/participants/CON-2005/brief", params={"accountId": "ACC-1002"}).json()
    assert card["contact"]["id"] == "CON-2005"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`
Expected: FAIL (`ModuleNotFoundError: app.api.routes`).

- [ ] **Step 3: Implement `api/routes.py`**

```python
"""Structured REST endpoints (under /api). Share the engine with the agent tools."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

from app import config
from app.data.repository import load_repository
from app.generation.brief import build_account_brief
from app.generation.participant import build_participant_card
from app.risk.engine import compute_risk

router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def get_repo():
    return load_repository(config.CRM_XLSX_PATH, config.MEETINGS_DIR)


def _make_llm():
    from app.llm.openrouter_client import OpenRouterClient
    return OpenRouterClient()


@lru_cache(maxsize=1)
def get_llm():
    return _make_llm()


_brief_cache: dict[str, dict] = {}


@router.get("/health")
def health():
    return {"status": "ok", "model": config.OPENROUTER_MODEL}


@router.get("/accounts")
def accounts():
    repo = get_repo()
    out = []
    for a in repo.list_accounts():
        risk = compute_risk(repo, a.id, config.NOW)
        out.append({"id": a.id, "name": a.name, "type": a.type, "tier": a.tier,
                    "status": a.status, "aum_with_cg_mm": a.aum_with_cg_mm,
                    "participant_count": len(repo.contacts_for_account(a.id)),
                    "overall_risk": risk.severity, "risk_score": round(risk.overall, 3)})
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


@router.get("/accounts/{account_id}/brief")
def account_brief(account_id: str):
    repo = get_repo()
    if repo.get_account(account_id) is None:
        raise HTTPException(404, f"Unknown account {account_id}")
    if account_id not in _brief_cache:
        _brief_cache[account_id] = build_account_brief(repo, account_id, get_llm(), config.NOW).model_dump()
    return _brief_cache[account_id]


@router.get("/accounts/{account_id}/participants")
def participants(account_id: str):
    repo = get_repo()
    return [{"contact_id": c.id, "name": c.name, "title": c.title, "role": c.role}
            for c in repo.contacts_for_account(account_id)]


@router.get("/participants/{contact_id}/brief")
def participant_brief(contact_id: str, accountId: str = Query(...)):
    repo = get_repo()
    if repo.get_contact(contact_id) is None:
        raise HTTPException(404, f"Unknown contact {contact_id}")
    return build_participant_card(repo, contact_id, accountId, get_llm(), config.NOW).model_dump()


@router.get("/accounts/{account_id}/meetings")
def meetings(account_id: str):
    repo = get_repo()
    return [{"id": m.id, "date": str(m.date), "type": m.type, "title": m.title, "summary": m.summary}
            for m in repo.meetings_for_account(account_id)]


@router.get("/meetings/{meeting_id}")
def meeting(meeting_id: str):
    m = get_repo().get_meeting(meeting_id)
    if m is None:
        raise HTTPException(404, f"Unknown meeting {meeting_id}")
    return m.model_dump()
```

- [ ] **Step 4: Implement `api/chat.py`**

```python
"""POST /api/chat -> the OpenRouter ReAct agent (lazy-built, per-thread memory)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app import config
from app.agent.runtime import build_agent
from app.api.routes import get_llm, get_repo

router = APIRouter(prefix="/api")
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent(get_repo(), get_llm(), config.NOW)
    return _agent


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


@router.post("/chat")
def chat(req: ChatRequest):
    try:
        result = _get_agent().invoke(
            {"messages": [HumanMessage(content=req.message)]},
            config={"configurable": {"thread_id": req.thread_id}})
        return {"reply": result["messages"][-1].content}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 5: Rewrite `app/main.py` (replace the minimal version)**

```python
"""FastAPI app: mounts the REST router and the chat agent under /api."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import chat, routes

app = FastAPI(title="Pre-Meeting Brief Copilot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(routes.router)
app.include_router(chat.router)


@app.on_event("startup")
def _prewarm():
    if not config.PREWARM:
        return
    repo = routes.get_repo()
    for a in repo.list_accounts():
        try:
            routes.account_brief(a.id)
        except Exception:
            pass
```

- [ ] **Step 6: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Manual smoke (real OpenRouter; needs network + key)**

Run (separate terminal): `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`
Then: `curl -s -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d "{\"message\":\"Brief me on Calderon\",\"thread_id\":\"t1\"}"`
Expected: JSON `{"reply": "...grounded brief..."}`. (If the free model is flaky, the REST `/api/accounts/ACC-1002/brief` still returns a guarded brief with template fallback.)

- [ ] **Step 8: Commit**

```powershell
git add backend/app/api/ backend/app/main.py backend/tests/test_api.py
git commit -m "feat: REST endpoints + /api/chat agent + app wiring (supersedes minimal main)"
```

### Task A8: Preview viewer

**Files:** Create `backend/preview.html`

- [ ] **Step 1: Implement a minimal self-test page**

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>Brief preview</title>
<style>body{font:14px system-ui;margin:2rem;max-width:780px}button{margin:.2rem}pre{white-space:pre-wrap;background:#f6f6f6;padding:1rem;border-radius:8px}</style>
</head><body>
<h1>Pre-Meeting Brief — preview</h1>
<div id="accts"></div>
<pre id="out">Pick an account…</pre>
<script>
const API = 'http://localhost:8000/api';
async function load(){
  const accts = await (await fetch(`${API}/accounts`)).json();
  const box = document.getElementById('accts');
  accts.forEach(a=>{const b=document.createElement('button');b.textContent=`${a.id} (${a.overall_risk})`;b.onclick=()=>show(a.id);box.appendChild(b);});
}
async function show(id){
  const b = await (await fetch(`${API}/accounts/${id}/brief`)).json();
  document.getElementById('out').textContent = JSON.stringify(b, null, 2);
}
load();
</script>
</body></html>
```

- [ ] **Step 2: Verify**

Run server (Task A7 Step 7), open `backend/preview.html` in a browser, click an account. Expected: JSON brief renders.

- [ ] **Step 3: Commit**

```powershell
git add backend/preview.html
git commit -m "feat: standalone brief preview page"
```

---

# Track B — Offline transcript generation (Ollama)

### Task B1: Ollama client

**Files:** Create `backend/app/llm/ollama_client.py`

- [ ] **Step 1: Implement**

```python
"""Offline-generation LLM (Ollama only). Local, no network/proxy/credits."""
from __future__ import annotations

from langchain_ollama import ChatOllama

from app import config
from app.llm.base import parse_json_object


class OllamaClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model_name = model or config.OLLAMA_MODEL
        self._chat = ChatOllama(
            model=self.model_name, base_url=base_url or config.OLLAMA_BASE_URL,
            temperature=0.4, format="json",
        )

    def generate_json(self, system: str, user: str) -> dict:
        resp = self._chat.invoke([("system", system), ("human", user)])
        return parse_json_object(getattr(resp, "content", "") or "")
```

- [ ] **Step 2: Smoke test (needs Ollama running locally)**

Run:
```powershell
.\.venv\Scripts\python.exe -c "from app.llm.ollama_client import OllamaClient; c=OllamaClient(model='qwen2.5-coder:7b'); print(c.generate_json('Return JSON.', 'Give {\"ok\": true}'))"
```
Expected: a dict like `{'ok': True}`. (If `qwen2.5:7b-instruct` isn't pulled, use `qwen2.5-coder:7b` which is already present, or `ollama pull qwen2.5:7b-instruct`.)

- [ ] **Step 3: Commit**

```powershell
git add backend/app/llm/ollama_client.py
git commit -m "feat: local Ollama client for offline generation"
```

### Task B2: Meeting generator + validation

**Files:** Create `backend/app/generation/meeting_prompts.py`, `backend/scripts/__init__.py` (empty), `backend/scripts/generate_meetings.py`, `backend/tests/test_generator.py`

- [ ] **Step 1: Write the failing test `tests/test_generator.py`**

```python
from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository
from scripts.generate_meetings import build_meeting_record


def test_build_meeting_record_validates_participants():
    repo = load_repository(CRM_XLSX_PATH, MEETINGS_DIR)
    acc = repo.get_account("ACC-1002")
    contacts = repo.contacts_for_account("ACC-1002")
    act = repo.activities_for_account("ACC-1002")[0]
    raw = {
        "summary": "Discussed the mandate.",
        "decisions": [{"text": "Proceed", "by": "Patricia Schmidt"}],
        "action_items": [{"text": "Send fees", "owner": "Diane Okafor", "status": "open"}],
        "participant_interests": {contacts[0].name: ["fees"]},
        "transcript_excerpt": [{"speaker": "X", "text": "hi"}],
        "participants": [contacts[0].name, "Nonexistent Person"],  # invalid name dropped
    }
    rec = build_meeting_record(act, acc, contacts, raw, index=1)
    assert rec.id.startswith("MTG-1002-")
    assert rec.date == act.date
    assert contacts[0].id in rec.participants            # name resolved to ID
    assert all(p in {c.id for c in contacts} for p in rec.participants)  # invalid dropped
    assert contacts[0].id in rec.participant_interests   # interests re-keyed to ID
    assert rec.synthetic is True
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_generator.py -q`
Expected: FAIL (`ModuleNotFoundError: scripts.generate_meetings`).

- [ ] **Step 3: Implement `generation/meeting_prompts.py`**

```python
"""Prompt for synthesizing a single prior meeting from a real Activity seed."""
from __future__ import annotations

import json

MEETING_SYSTEM = (
    "You generate a realistic but SYNTHETIC record of a PAST institutional client "
    "meeting for a mock CRM demo. Stay consistent with the provided facts (account, "
    "contacts, open mandates). Do not contradict them. Reference people by their real "
    "names from the contacts list. Return JSON: {\"summary\": str, "
    "\"decisions\": [{\"text\": str, \"by\": contact_name}], "
    "\"action_items\": [{\"text\": str, \"owner\": str, \"status\": \"open\"|\"done\"}], "
    "\"participant_interests\": {contact_name: [str]}, "
    "\"transcript_excerpt\": [{\"speaker\": contact_name, \"text\": str}], "
    "\"participants\": [contact_name]}."
)


def build_meeting_user(seed: dict) -> str:
    return "SEED FACTS (JSON):\n" + json.dumps(seed, indent=2, default=str)
```

- [ ] **Step 4: Implement `scripts/generate_meetings.py`**

```python
"""Offline: synthesize prior-meeting fixtures with local Ollama, seeded from real
Activities. Validates to MeetingRecord and writes data/generated/meetings/<ACC>.json.

Run:  .\.venv\Scripts\python.exe scripts\generate_meetings.py [ACC-1002 ACC-1017 ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app import config
from app.data.repository import Repository, load_repository
from app.domain.models import (ActionItem, Activity, Decision, MeetingRecord,
                                TranscriptTurn)
from app.generation.meeting_prompts import MEETING_SYSTEM, build_meeting_user

MEETING_TYPES = {"Meeting", "Call", "Portfolio Review", "Conference"}


def _name_to_id(contacts) -> dict[str, str]:
    return {c.name: c.id for c in contacts}


def build_meeting_record(activity: Activity, account, contacts, raw: dict, index: int) -> MeetingRecord:
    n2i = _name_to_id(contacts)
    valid_ids = set(n2i.values())

    def to_id(name):
        return n2i.get(name) or (name if name in valid_ids else None)

    participants = [pid for pid in (to_id(p) for p in raw.get("participants", [])) if pid]
    if not participants and activity.contact:
        pid = to_id(activity.contact)
        if pid:
            participants = [pid]

    interests = {}
    for name, items in (raw.get("participant_interests") or {}).items():
        cid = to_id(name)
        if cid and isinstance(items, list):
            interests[cid] = [str(x) for x in items]

    decisions = [Decision(text=d.get("text", ""), by=to_id(d.get("by")))
                 for d in (raw.get("decisions") or []) if d.get("text")]
    action_items = [ActionItem(text=a.get("text", ""), owner=a.get("owner"),
                               status=a.get("status", "open"))
                    for a in (raw.get("action_items") or []) if a.get("text")]
    transcript = [TranscriptTurn(speaker=t.get("speaker", "?"), text=t.get("text", ""))
                  for t in (raw.get("transcript_excerpt") or []) if t.get("text")]

    acc_num = account.id.split("-")[-1]
    return MeetingRecord(
        id=f"MTG-{acc_num}-{index:02d}",
        date=activity.date or config.NOW,
        type=activity.type, title=activity.subject or "Client meeting",
        participants=participants, summary=raw.get("summary", "").strip(),
        decisions=decisions, action_items=action_items,
        participant_interests=interests, transcript_excerpt=transcript,
        source_activity=activity.id, synthetic=True,
    )


def generate_for_account(repo: Repository, account_id: str, llm) -> dict:
    account = repo.get_account(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    seeds = [a for a in repo.activities_for_account(account_id) if (a.type or "") in MEETING_TYPES]
    meetings = []
    for i, act in enumerate(seeds, start=1):
        seed = {
            "account": {"name": account.name, "type": account.type, "status": account.status,
                        "primary_strategy": account.primary_strategy, "consultant": account.consultant},
            "contacts": [{"name": c.name, "title": c.title, "role": c.role} for c in contacts],
            "open_mandates": [{"opportunity": o.opportunity, "strategy": o.strategy,
                               "size_mm": o.mandate_size_mm, "stage": o.stage} for o in opps],
            "activity": {"date": str(act.date), "type": act.type, "subject": act.subject,
                         "contact": act.contact, "next_step": act.next_step},
        }
        try:
            raw = llm.generate_json(MEETING_SYSTEM, build_meeting_user(seed))
        except Exception:
            raw = {}
        meetings.append(build_meeting_record(act, account, contacts, raw, i).model_dump(mode="json"))
    return {"account_id": account_id, "meetings": meetings}


def main(argv: list[str]) -> None:
    repo = load_repository(config.CRM_XLSX_PATH, config.MEETINGS_DIR)
    from app.llm.ollama_client import OllamaClient
    try:
        llm = OllamaClient()                       # default qwen2.5:7b-instruct
    except Exception:
        llm = OllamaClient(model=config.OLLAMA_MODEL_FALLBACK)
    targets = argv or [a.id for a in repo.list_accounts()]
    out_dir = Path(config.MEETINGS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for aid in targets:
        data = generate_for_account(repo, aid, llm)
        (out_dir / f"{aid}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"wrote {aid}.json ({len(data['meetings'])} meetings)")


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 5: Run, expect PASS**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_generator.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```powershell
git add backend/app/generation/meeting_prompts.py backend/scripts/ backend/tests/test_generator.py
git commit -m "feat: offline meeting generator + record validation (name->ID, schema)"
```

### Task B3: Generate, review, and commit fixtures (integration — needs Ollama)

**Files:** Overwrite/create `backend/data/generated/meetings/*.json`

- [ ] **Step 1: (Optional) pull a general instruct model for nicer prose**

Run: `ollama pull qwen2.5:7b-instruct`  (skip to use the already-present `qwen2.5-coder:7b` — then `set OLLAMA_MODEL=qwen2.5-coder:7b`).

- [ ] **Step 2: Generate the demo accounts first**

Run: `.\.venv\Scripts\python.exe scripts\generate_meetings.py ACC-1002 ACC-1017`
Expected: `wrote ACC-1002.json (...)` and `wrote ACC-1017.json (...)`.

- [ ] **Step 3: Eyeball the output** — open `backend/data/generated/meetings/ACC-1002.json`; confirm summaries are coherent, participants are real `CON-*` IDs, no contradictions with the CRM. Re-run if a record is poor (it's deterministic per seed but `temperature>0`; lower `temperature` in `ollama_client.py` if needed).

- [ ] **Step 4: Generate the rest (optional, cheap)**

Run: `.\.venv\Scripts\python.exe scripts\generate_meetings.py`
Expected: one file per account.

- [ ] **Step 5: Commit the fixtures**

```powershell
git add backend/data/generated/meetings/
git commit -m "data: synthetic prior-meeting fixtures (Ollama, frozen)"
```

---

# Integration

### Task I1: End-to-end with real fixtures

**Files:** Modify `backend/tests/test_api.py` (append)

- [ ] **Step 1: Add end-to-end assertions for both demo accounts**

```python
def test_e2e_demo_accounts(monkeypatch):
    from tests.conftest import StubLLM
    import app.api.routes as routes
    monkeypatch.setattr(routes, "_make_llm", lambda: StubLLM({}))
    routes.get_repo.cache_clear()       # pick up freshly generated fixtures
    routes._brief_cache.clear()
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for aid in ("ACC-1002", "ACC-1017"):
        b = c.get(f"/api/accounts/{aid}/brief").json()
        assert b["headline"] and b["risk_flags"]
        ms = c.get(f"/api/accounts/{aid}/meetings").json()
        assert isinstance(ms, list)
```

- [ ] **Step 2: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Live demo smoke** — run backend (`uvicorn app.main:app --port 8000`) + UI (`cd UI; npm install; npm run dev` → http://localhost:3000). In the Sage Agent chat, send "Brief me on Calderon" and "What should I know about Lisa Schmidt at Calderon?" Expected: grounded replies.

- [ ] **Step 4: Commit**

```powershell
git add backend/tests/test_api.py
git commit -m "test: end-to-end brief + meetings for demo accounts"
```

---

## Self-review (completed by plan author)

- **Spec coverage:** grounding store (0.4), synthetic meetings offline/Ollama (B1–B3), risk math (A2), LLM-phrasing+guard (A3–A5), `/api/chat` agent + tools (A6, A7), REST endpoints under `/api` (A7), CORS/proxy/port-3000 (A7), cache + prewarm (A7), preview (A8), parallel tracks (structure). ✅
- **Placeholder scan:** no TBD/TODO; every code step has complete code; every test has assertions. ✅
- **Type consistency:** `LLMClient.generate_json(system, user)`, `compute_risk(repo, id, now) -> RiskResult`, `RiskComponent.key/score/severity/evidence/sources`, `guard_statements(stmts, valid_sources, context_numbers)`, repository method names — all consistent across A2–A7, B2. ✅
- **Known risk:** the live `/api/chat` path depends on the free OpenRouter model behaving; the REST briefs degrade gracefully via template fallback and are demoable without the model. Note surfaced in Task A7.
