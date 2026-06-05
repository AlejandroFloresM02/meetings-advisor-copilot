"""POST /api/chat -> the OpenRouter ReAct agent (lazy-built, per-thread memory).

Accepts an optional `context` transcript (sent by the UI's Briefing panel) — the
in-meeting group-chat messages. When present, the transcript is folded into the
agent prompt so answers are grounded in the live conversation *and* the agent's
CRM tools (account brief, participant card, meeting history). This makes
`/api/chat` a drop-in superset of `OpenRouter_Agent/server.py`.
"""
from __future__ import annotations

from typing import Any

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
    # Optional in-meeting transcript from the UI Briefing panel. Each item is a
    # message dict: {user, position, hour?, content, ...} (extra keys ignored).
    context: list[dict[str, Any]] | None = None


def _format_transcript(context: list[dict[str, Any]]) -> str:
    """Render the conversation messages into a readable transcript."""
    lines = []
    for m in context:
        who = m.get("user", "Unknown")
        position = m.get("position")
        speaker = f"{who} ({position})" if position else who
        hour = m.get("hour", "")
        prefix = f"[{hour}] " if hour else ""
        lines.append(f"{prefix}{speaker}: {m.get('content', '')}")
    return "\n".join(lines)


def _grounded_message(message: str, context: list[dict[str, Any]]) -> str:
    """Embed the transcript alongside the question; allow CRM tool use too."""
    transcript = _format_transcript(context)
    return (
        "You are assisting a Capital Group relationship manager during a live "
        "meeting. The conversation so far is below. Use it as primary context, "
        "and call your CRM tools for account, participant, or meeting-history "
        "facts when they add value. Ground every statement in the transcript or "
        "tool results; never invent numbers or claims.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"QUESTION: {message}"
    )


@router.post("/chat")
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    content = (
        _grounded_message(req.message, req.context)
        if req.context
        else req.message
    )
    try:
        result = _get_agent().invoke(
            {"messages": [HumanMessage(content=content)]},
            config={"configurable": {"thread_id": req.thread_id}})
        return {"reply": result["messages"][-1].content}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
