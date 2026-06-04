# Laguna Agent

A minimal LangChain agent that uses OpenRouter's **free** `poolside/laguna-m.1:free`
model. Built with the officially recommended integration:

- [`langchain-openrouter`](https://docs.langchain.com/oss/python/integrations/chat/openrouter) → `ChatOpenRouter` (the chat model)
- [`langchain` v1](https://docs.langchain.com/oss/python/langchain/agents) → `create_agent` (a prebuilt tool-calling agent)

The agent ships with two example tools (`get_current_time`, `calculator`) and keeps
conversation history for the session via an in-memory checkpointer.

## Requirements

- **Python 3.10+** (this project was set up with 3.12; `langchain-openrouter` does not support 3.9)
- A free OpenRouter API key: https://openrouter.ai/keys

## Setup

```powershell
# 1. Create / reuse the virtual environment (already created as .venv)
py -3.12 -m venv .venv

# 2. Install dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Add your API key
copy .env.example .env
#    then edit .env and paste your key
```

## Run

```powershell
.\.venv\Scripts\python.exe agent.py
```

Then chat in the terminal:

```
you> what time is it, and what is 19 * 23?
bot> ...
you> exit
```

## Web UI (React)

A React chat interface lives in [`UI/`](UI/) (Vite). It talks to the agent through a
small FastAPI backend ([`server.py`](server.py)). You need **two terminals**.

**Terminal 1 — backend** (serves the agent at http://localhost:8000):

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

**Terminal 2 — frontend** (Vite dev server at http://localhost:5173):

```powershell
cd UI
npm install        # first time only
npm run dev
```

Open http://localhost:5173 and chat. The Vite dev server proxies `/api/*` to the
backend, so there are no CORS issues. Each browser tab gets its own `thread_id`,
so the agent remembers the conversation within that tab.

> Requires **Node.js 18+** (this project was set up with Node 24). If `npm` is
> not found, open a fresh terminal so the updated PATH takes effect.

## Adding your own tools

Define a function, decorate it with `@tool`, and add it to the `TOOLS` list in
[`agent.py`](agent.py). The model decides when to call it.

```python
@tool
def reverse_text(text: str) -> str:
    """Reverse the given text."""
    return text[::-1]

TOOLS = [get_current_time, calculator, reverse_text]
```
