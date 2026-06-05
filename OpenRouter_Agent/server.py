"""
FastAPI backend that exposes the LangChain agent over HTTP for the React UI.

Run it with:
    .venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8000

Endpoints:
    GET  /api/health  -> basic status + model name
    POST /api/chat    -> { "message": str, "thread_id": str } -> { "reply": str }

Conversation history is kept per `thread_id` by the agent's in-memory checkpointer,
so the same browser session keeps context across messages.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent import MODEL, build_agent

# Built once on startup and reused across requests (the checkpointer lives here,
# so per-thread memory persists for the lifetime of the server).
_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    _agent = build_agent()
    yield


app = FastAPI(title="Laguna Agent API", lifespan=lifespan)

# Allow the Vite dev server to call us directly (the dev proxy makes this
# unnecessary, but it keeps things working if the UI is hosted elsewhere).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "web-session"
    # Optional conversation transcript the answer should be grounded in. Used by
    # the group-chat "Briefing" panel, which sends the meeting messages here.
    # Each item is a message object: {user, position, hour, content, ...}.
    context: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    reply: str


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
    """Embed the transcript alongside the user's question for the agent."""
    transcript = _format_transcript(context)
    return (
        "You are briefing a colleague on a team meeting conversation. Use the "
        "transcript below as your source of truth. If the answer is not in the "
        "transcript, say so plainly rather than guessing.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"QUESTION: {message}"
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    # When the UI sends conversation context (the Briefing panel), ground the
    # answer in that transcript; otherwise answer the message as-is.
    content = (
        _grounded_message(req.message, req.context) if req.context else req.message
    )
    try:
        result = _agent.invoke(
            {"messages": [HumanMessage(content=content)]},
            config={"configurable": {"thread_id": req.thread_id}},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent error: {exc}") from exc
    return ChatResponse(reply=result["messages"][-1].content)
