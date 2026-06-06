"""LLM extraction port (spec §6) + record/replay.

`extract(system, user) -> dict` mirrors app.llm's generate_json. The offline
suite uses stub/replay extractors; the live `OpenRouterLlmExtractor` wraps
app.llm lazily (its langchain stack is an ingest extra, not a test dep).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol


class LlmExtractor(Protocol):
    def extract(self, system: str, user: str) -> dict: ...


def llm_key(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\x00{user}".encode()).hexdigest()[:16]


class ReplayLlmExtractor:
    def __init__(self, cassette_dir: Path):
        self.dir = Path(cassette_dir)

    def extract(self, system: str, user: str) -> dict:
        path = self.dir / "llm" / f"{llm_key(system, user)}.json"
        if not path.exists():
            raise FileNotFoundError(f"no llm cassette at {path}")
        return json.loads(path.read_text(encoding="utf-8"))


class RecordingLlmExtractor:
    def __init__(self, inner: LlmExtractor, cassette_dir: Path):
        self.inner = inner
        self.dir = Path(cassette_dir)

    def extract(self, system: str, user: str) -> dict:
        out = self.inner.extract(system, user)
        path = self.dir / "llm" / f"{llm_key(system, user)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        return out


class OpenRouterLlmExtractor:
    """Live extractor wrapping app.llm (imported lazily — langchain is an extra)."""

    def __init__(self) -> None:
        from app.llm.openrouter_client import OpenRouterClient

        self._client = OpenRouterClient()

    def extract(self, system: str, user: str) -> dict:
        return self._client.generate_json(system, user)
