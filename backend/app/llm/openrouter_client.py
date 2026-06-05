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
        kw["client"] = httpx.Client(
            headers=headers, follow_redirects=True, verify=False
        )
        kw["async_client"] = httpx.AsyncClient(
            headers=headers, follow_redirects=True, verify=False
        )
        if self.request_timeout is not None:
            kw["timeout_ms"] = self.request_timeout
        if self.max_retries > 0:
            kw["retry_config"] = RetryConfig(
                strategy="backoff",
                backoff=BackoffStrategy(
                    initial_interval=500,
                    max_interval=60000,
                    exponent=1.5,
                    max_elapsed_time=self.max_retries * 150_000,
                ),
                retry_connection_errors=True,
            )
        return openrouter.OpenRouter(**kw)


def build_chat_model() -> CertificateBypassingChatOpenRouter:
    return CertificateBypassingChatOpenRouter(
        model=config.OPENROUTER_MODEL,
        temperature=0.3,
        max_tokens=1024,
        max_retries=2,
        app_title="Sage Brief Copilot",
    )


class OpenRouterClient:
    """generate_json over the TLS-bypass chat model."""

    def __init__(self, model: CertificateBypassingChatOpenRouter | None = None):
        self._model = model or build_chat_model()

    def generate_json(self, system: str, user: str) -> dict:
        try:
            resp = self._model.invoke(
                [
                    SystemMessage(
                        content=system
                        + " Respond with a single valid JSON object and nothing else."
                    ),
                    HumanMessage(content=user),
                ]
            )
            return parse_json_object(getattr(resp, "content", "") or "")
        except Exception:
            return {}
