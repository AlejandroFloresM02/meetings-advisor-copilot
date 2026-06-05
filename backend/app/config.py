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

CRM_XLSX_PATH = Path(
    os.getenv("CRM_XLSX_PATH", REPO_ROOT / "Capital_Group_CRM_mock.xlsx")
)
MEETINGS_DIR = Path(
    os.getenv("MEETINGS_DIR", BACKEND_ROOT / "data" / "generated" / "meetings")
)
UI_PUBLIC_DIR = REPO_ROOT / "UI" / "public"
# Live, in-progress meeting conversations shown in the UI (account_id -> file in UI/public).
LIVE_CONVERSATIONS = {"ACC-1002": "calderon-conversation.json"}


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
    "coverage": 0.18,
    "recency": 0.14,
    "status": 0.16,
    "aum_vs_peers": 0.12,
    "pipeline": 0.16,
    "loss": 0.08,
    "consultant": 0.06,
    "open_actions": 0.10,
}
