"""Build the OpenRouter ReAct agent with grounded tools + per-thread memory."""

from __future__ import annotations

from datetime import date

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import tools as agent_tools
from app.llm.openrouter_client import build_chat_model

SYSTEM_PROMPT = (
    "You are Sage, a pre-meeting brief copilot for Capital Group institutional "
    "relationship managers. For ANY question about an account, person, meeting, or "
    "risk, you MUST call the appropriate tool and base your answer only on its output. "
    "Use get_current_meeting for what is being said in the meeting right now, and "
    "get_meeting_history for past meetings. "
    "Never invent numbers, names, or facts. Be concise and professional."
)


def build_agent(repo, llm, now: date):
    agent_tools.configure(repo, llm, now)
    model = build_chat_model()
    return create_agent(
        model=model,
        tools=agent_tools.TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )
