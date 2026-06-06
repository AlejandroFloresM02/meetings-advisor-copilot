"""V2 config: snapshot paths + the reference 'now' date."""

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
