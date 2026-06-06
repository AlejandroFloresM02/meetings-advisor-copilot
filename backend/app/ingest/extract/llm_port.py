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


def _json_object(text: str) -> dict:
    """Parse a single JSON object from model text (robust to fences / stray prose)."""
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


class OllamaLlmExtractor:
    """Local Ollama extractor (spec §6 live path) — key-free, no cost.

    Speaks Ollama's /api/chat over httpx with ``format=json``, so it needs no
    langchain stack — only the core ``httpx`` dep. Defaults to the ``OLLAMA_URL``
    env var or localhost:11434. ``client`` is injectable for offline tests.
    """

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        base_url: str | None = None,
        client=None,
        timeout: float = 180.0,
        temperature: float = 0.0,
    ) -> None:
        import os

        self.model = model
        self.base_url = (
            base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        ).rstrip("/")
        self._client = client
        self.timeout = timeout
        self.temperature = temperature

    def _http(self):
        if self._client is not None:
            return self._client
        import httpx

        return httpx.Client(timeout=self.timeout)

    def extract(self, system: str, user: str) -> dict:
        resp = self._http().post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system
                        + " Respond with a single valid JSON object and nothing else.",
                    },
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": self.temperature},
            },
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "") or ""
        return _json_object(content)
