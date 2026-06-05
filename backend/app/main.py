"""FastAPI app: mounts the REST router and the chat agent under /api."""

from __future__ import annotations

import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import chat, routes

app = FastAPI(title="Pre-Meeting Brief Copilot")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(routes.router)
app.include_router(chat.router)


@app.on_event("startup")
def _prewarm():
    if not config.PREWARM:
        return
    repo = routes.get_repo()
    for a in repo.list_accounts():
        with contextlib.suppress(Exception):
            routes.account_brief(a.id)
