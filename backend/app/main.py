"""FastAPI backend for the Sage Agent UI.

Exposes ``POST /api/chat`` wrapping the OpenRouter ReAct agent (TLS-bypass client
lifted from ``OpenRouter_Agent/agent.py``). This is the minimal version that makes
the existing ``UI/`` Sage-Agent chat work; grounded CRM tools (brief, participant,
meeting history, risk) are added on top of this in Track A.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Reuse the API key already configured for the teammate's agent — no secret copy.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / "OpenRouter_Agent" / ".env")
load_dotenv(_REPO_ROOT / "backend" / ".env")  # optional local override

from langchain.agents import create_agent  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openrouter import ChatOpenRouter  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

MODEL = os.getenv("OPENROUTER_MODEL", "poolside/laguna-m.1:free")


class CertificateBypassingChatOpenRouter(ChatOpenRouter):
    """ChatOpenRouter variant that disables TLS verification (corporate proxy)."""

    def _build_client(self) -> Any:
        import httpx
        import openrouter
        from openrouter.utils import BackoffStrategy, RetryConfig

        client_kwargs: dict[str, Any] = {
            "api_key": self.openrouter_api_key.get_secret_value(),  # type: ignore[union-attr]
        }
        if self.openrouter_api_base:
            client_kwargs["server_url"] = self.openrouter_api_base

        extra_headers: dict[str, str] = {}
        if self.app_title:
            extra_headers["X-Title"] = self.app_title

        client_kwargs["client"] = httpx.Client(
            headers=extra_headers, follow_redirects=True, verify=False
        )
        client_kwargs["async_client"] = httpx.AsyncClient(
            headers=extra_headers, follow_redirects=True, verify=False
        )
        if self.request_timeout is not None:
            client_kwargs["timeout_ms"] = self.request_timeout
        if self.max_retries > 0:
            client_kwargs["retry_config"] = RetryConfig(
                strategy="backoff",
                backoff=BackoffStrategy(
                    initial_interval=500,
                    max_interval=60000,
                    exponent=1.5,
                    max_elapsed_time=self.max_retries * 150_000,
                ),
                retry_connection_errors=True,
            )
        return openrouter.OpenRouter(**client_kwargs)


@tool
def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return _dt.datetime.now().isoformat(timespec="seconds")


SYSTEM_PROMPT = (
    "You are Sage, a pre-meeting brief copilot for Capital Group institutional "
    "relationship managers. Be concise and professional. "
    "(Grounded CRM tools — account briefs, participant cards, meeting history, "
    "risk flags — are being wired in; for now answer directly.)"
)


def _build_agent():
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set (looked in OpenRouter_Agent/.env and backend/.env)."
        )
    model = CertificateBypassingChatOpenRouter(
        model=MODEL, temperature=0.3, max_tokens=1024, max_retries=2,
        app_title="Sage Brief Copilot",
    )
    return create_agent(
        model=model,
        tools=[get_current_time],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )


app = FastAPI(title="Pre-Meeting Brief Copilot")
# Permissive CORS for direct calls; in dev the Vite proxy means the browser
# only talks to :3000 anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_agent = None


def agent():
    """Lazily build the agent so the app imports even before the key/model is ready."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        result = agent().invoke(
            {"messages": [HumanMessage(content=req.message)]},
            config={"configurable": {"thread_id": req.thread_id}},
        )
        return {"reply": result["messages"][-1].content}
    except Exception as exc:  # surface as JSON {detail} for the UI
        raise HTTPException(status_code=500, detail=str(exc))
