"""Structured REST endpoints (under /api). Share the engine with the agent tools."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

from app import config
from app.data.repository import load_repository
from app.generation.brief import build_account_brief
from app.generation.participant import build_participant_card
from app.risk.engine import compute_risk

router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def get_repo():
    return load_repository(config.CRM_XLSX_PATH, config.MEETINGS_DIR)


def _make_llm():
    from app.llm.openrouter_client import OpenRouterClient

    return OpenRouterClient()


@lru_cache(maxsize=1)
def get_llm():
    return _make_llm()


_brief_cache: dict[str, dict] = {}


@router.get("/health")
def health():
    return {"status": "ok", "model": config.OPENROUTER_MODEL}


@router.get("/accounts")
def accounts():
    repo = get_repo()
    out = []
    for a in repo.list_accounts():
        risk = compute_risk(repo, a.id, config.NOW)
        out.append(
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "tier": a.tier,
                "status": a.status,
                "aum_with_cg_mm": a.aum_with_cg_mm,
                "participant_count": len(repo.contacts_for_account(a.id)),
                "overall_risk": risk.severity,
                "risk_score": round(risk.overall, 3),
            }
        )
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


@router.get("/accounts/{account_id}/brief")
def account_brief(account_id: str):
    repo = get_repo()
    if repo.get_account(account_id) is None:
        raise HTTPException(404, f"Unknown account {account_id}")
    if account_id not in _brief_cache:
        _brief_cache[account_id] = build_account_brief(
            repo, account_id, get_llm(), config.NOW
        ).model_dump()
    return _brief_cache[account_id]


@router.get("/accounts/{account_id}/participants")
def participants(account_id: str):
    repo = get_repo()
    return [
        {"contact_id": c.id, "name": c.name, "title": c.title, "role": c.role}
        for c in repo.contacts_for_account(account_id)
    ]


@router.get("/participants/{contact_id}/brief")
def participant_brief(contact_id: str, account_id: str = Query(..., alias="accountId")):
    repo = get_repo()
    if repo.get_contact(contact_id) is None:
        raise HTTPException(404, f"Unknown contact {contact_id}")
    return build_participant_card(
        repo, contact_id, account_id, get_llm(), config.NOW
    ).model_dump()


@router.get("/accounts/{account_id}/meetings")
def meetings(account_id: str):
    repo = get_repo()
    return [
        {
            "id": m.id,
            "date": str(m.date),
            "type": m.type,
            "title": m.title,
            "summary": m.summary,
        }
        for m in repo.meetings_for_account(account_id)
    ]


@router.get("/meetings/{meeting_id}")
def meeting(meeting_id: str):
    m = get_repo().get_meeting(meeting_id)
    if m is None:
        raise HTTPException(404, f"Unknown meeting {meeting_id}")
    return m.model_dump()
