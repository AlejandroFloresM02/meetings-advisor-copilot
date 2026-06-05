"""Offline-generation LLM (Ollama only). Local, no network/proxy/credits."""

from __future__ import annotations

from langchain_ollama import ChatOllama

from app import config
from app.llm.base import parse_json_object


class OllamaClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model_name = model or config.OLLAMA_MODEL
        self._chat = ChatOllama(
            model=self.model_name,
            base_url=base_url or config.OLLAMA_BASE_URL,
            temperature=0.4,
            format="json",
        )

    def generate_json(self, system: str, user: str) -> dict:
        resp = self._chat.invoke([("system", system), ("human", user)])
        return parse_json_object(getattr(resp, "content", "") or "")
