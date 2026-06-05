"""
Simple LangChain agent powered by OpenRouter's free Poolside Laguna M.1 model.

Uses the officially recommended integration:
  - langchain-openrouter  -> ChatOpenRouter   (the chat model)
  - langchain (v1)        -> create_agent     (the prebuilt ReAct-style agent)

Docs:
  https://docs.langchain.com/oss/python/integrations/chat/openrouter
  https://docs.langchain.com/oss/python/langchain/agents
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openrouter import ChatOpenRouter
from langgraph.checkpoint.memory import InMemorySaver

# Load OPENROUTER_API_KEY (and anything else) from a local .env file.
load_dotenv()

MODEL = "poolside/laguna-m.1:free"


class CertificateBypassingChatOpenRouter(ChatOpenRouter):
    """ChatOpenRouter variant that disables TLS certificate verification."""

    def _build_client(self) -> Any:
        """Build an OpenRouter SDK client with certificate checks disabled."""
        import httpx
        import openrouter
        from openrouter.utils import BackoffStrategy, RetryConfig

        client_kwargs: dict[str, Any] = {
            "api_key": self.openrouter_api_key.get_secret_value(),  # type: ignore[union-attr]
        }
        if self.openrouter_api_base:
            client_kwargs["server_url"] = self.openrouter_api_base

        extra_headers: dict[str, str] = {}
        if self.app_url:
            extra_headers["HTTP-Referer"] = self.app_url
        if self.app_title:
            extra_headers["X-Title"] = self.app_title
        if self.app_categories:
            extra_headers["X-OpenRouter-Categories"] = ",".join(self.app_categories)

        client_kwargs["client"] = httpx.Client(
            headers=extra_headers,
            follow_redirects=True,
            verify=False,
        )
        client_kwargs["async_client"] = httpx.AsyncClient(
            headers=extra_headers,
            follow_redirects=True,
            verify=False,
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


# --------------------------------------------------------------------------- #
# Tools — the agent decides when to call these. Add your own here.
# --------------------------------------------------------------------------- #
@tool
def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return _dt.datetime.now().isoformat(timespec="seconds")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression.

    Supports +, -, *, /, **, %, parentheses and floats, e.g. "3 * (4 + 5)".
    """
    allowed = set("0123456789.+-*/%() ")
    if not set(expression) <= allowed:
        return "Error: expression contains characters that are not allowed."
    try:
        # No builtins -> a constrained, safe numeric eval.
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:
        return f"Error: {exc}"
    return str(result)


TOOLS = [get_current_time, calculator]

SYSTEM_PROMPT = (
    "You are a concise, helpful assistant. "
    "Use the provided tools when they help answer accurately "
    "(e.g. for the current time or for arithmetic). "
    "Otherwise answer directly."
)


def build_agent():
    """Construct and return the compiled agent graph."""
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
            "your key from https://openrouter.ai/keys"
        )

    model = CertificateBypassingChatOpenRouter(
        model=MODEL,
        temperature=0.3,
        max_tokens=1024,
        max_retries=2,
        # Optional but recommended by OpenRouter: identify your app for the
        # leaderboards. Safe to leave as-is or remove.
        app_title="LangChain Laguna Agent",
    )

    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        # In-memory conversation history (per thread_id) for this run.
        checkpointer=InMemorySaver(),
    )


def chat() -> None:
    """Run an interactive REPL chat loop with the agent."""
    agent = build_agent()
    config = {"configurable": {"thread_id": "cli-session"}}

    print(f"Agent ready — model: {MODEL}")
    print("Type your message. Commands: 'exit' / 'quit' to leave.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        result = agent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
        )
        # The agent returns the full message list; the last one is the reply.
        print(f"bot> {result['messages'][-1].content}\n")

    print("Goodbye.")


if __name__ == "__main__":
    chat()
