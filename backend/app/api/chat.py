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
