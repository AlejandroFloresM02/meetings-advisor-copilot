"""Assemble facts -> LLM phrasing -> guard -> AccountBrief, with template fallback."""

from __future__ import annotations

from datetime import date

from app import config
from app.domain.models import AccountBrief, RiskFlag, TalkingPoint
from app.generation.guard import extract_numbers, guard_statements, statement_supported
from app.generation.prompts import BRIEF_SYSTEM, build_brief_user
from app.risk.engine import compute_risk


def _valid_sources(acc, contacts, opps, activities, meetings) -> set[str]:
    return (
        {acc.id}
        | {c.id for c in contacts}
        | {o.id for o in opps}
        | {a.id for a in activities}
        | {m.id for m in meetings}
    )


def _context_numbers(acc, opps, risk, meetings) -> set[str]:
    parts = [c.evidence for c in risk.components]
    parts.append(f"{acc.aum_with_cg_mm}")
    parts += [
        f"{o.mandate_size_mm} {o.probability} {int(o.probability * 100)}" for o in opps
    ]
    for m in meetings:  # whitelist numbers that legitimately appear in meeting facts
        parts.append(m.summary)
        parts += [d.text for d in m.decisions]
        parts += [ai.text for ai in m.action_items]
    return extract_numbers(" ".join(parts))


def _derive_meeting(acc, opps, now: date) -> dict:
    open_opps = [o for o in opps if (o.stage or "") not in ("Won", "Lost")]
    open_opps.sort(key=lambda o: o.expected_close or date.max)
    purpose = (
        f"Advance {open_opps[0].opportunity}"
        if open_opps
        else f"Relationship review - {acc.name}"
    )
    return {"purpose": purpose, "date": now.isoformat(), "participant_count": None}


def _since_last_meeting(meetings) -> dict | None:
    if not meetings:
        return None
    last = max(meetings, key=lambda m: m.date)
    open_items = [
        {"text": ai.text, "sources": [last.id]}
        for ai in last.action_items
        if ai.status == "open"
    ]
    return {
        "summary": last.summary,
        "meeting_id": last.id,
        "date": last.date.isoformat(),
        "open_action_items": open_items,
    }


def _fallback_talking_points(acc, opps, meetings) -> list[TalkingPoint]:
    tps = []
    for o in opps:
        if (o.stage or "") not in ("Won", "Lost"):
            tps.append(
                TalkingPoint(
                    text=f"Advance {o.opportunity} (${o.mandate_size_mm:.0f}mm, {o.stage}, {int(o.probability * 100)}% prob).",
                    sources=[o.id],
                )
            )
    for m in meetings:
        for ai in m.action_items:
            if ai.status == "open":
                tps.append(
                    TalkingPoint(
                        text=f"Close prior commitment: {ai.text}.", sources=[m.id]
                    )
                )
    if not tps:
        tps.append(
            TalkingPoint(
                text=f"Reaffirm the relationship with {acc.name}.", sources=[acc.id]
            )
        )
    return tps[:5]


def build_account_brief(repo, account_id: str, llm, now: date) -> AccountBrief:
    acc = repo.get_account(account_id)
    if acc is None:
        raise KeyError(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    activities = repo.activities_for_account(account_id)
    meetings = repo.meetings_for_account(account_id)
    risk = compute_risk(repo, account_id, now)

    valid = _valid_sources(acc, contacts, opps, activities, meetings)
    ctx_nums = _context_numbers(acc, opps, risk, meetings)

    facts = {
        "account": acc.model_dump(),
        "fact_ids": sorted(valid),
        "risk_components": [c.model_dump() for c in risk.components],
        "open_pipeline": [
            o.model_dump() for o in opps if (o.stage or "") not in ("Won", "Lost")
        ],
        "recent_meetings": [
            {
                "id": m.id,
                "date": str(m.date),
                "summary": m.summary,
                "decisions": [d.model_dump() for d in m.decisions],
                "open_action_items": [
                    ai.text for ai in m.action_items if ai.status == "open"
                ],
            }
            for m in meetings
        ],
    }

    raw = {}
    try:
        raw = llm.generate_json(BRIEF_SYSTEM, build_brief_user(facts))
    except Exception:
        raw = {}

    tps_raw = (
        raw.get("talking_points") if isinstance(raw.get("talking_points"), list) else []
    )
    tps = [TalkingPoint(**s) for s in guard_statements(tps_raw, valid, ctx_nums)]
    if not tps:
        tps = _fallback_talking_points(acc, opps, meetings)

    expl = raw.get("risk_explanations") or {}
    flags = []
    for c in risk.components[:5]:
        e = expl.get(c.key) if isinstance(expl, dict) else None
        if e and not statement_supported(e, c.sources, valid, ctx_nums):
            e = None
        flags.append(
            RiskFlag(
                id=c.key,
                title=c.title,
                severity=c.severity,
                score=c.score,
                evidence=c.evidence,
                explanation=e,
                sources=c.sources,
            )
        )

    llm_headline = (raw.get("headline") or "").strip()
    if llm_headline and not statement_supported(llm_headline, [], valid, ctx_nums):
        llm_headline = (
            ""  # fabricated number in headline -> drop, fall back to template
        )
    headline = llm_headline or (
        f"{acc.tier or ''} {acc.status or ''} account; top risk: {risk.components[0].title.lower()}."
    )
    next_steps = [
        s for s in (raw.get("next_steps") or []) if isinstance(s, str) and s.strip()
    ]
    if not next_steps:
        next_steps = [
            ai.text for m in meetings for ai in m.action_items if ai.status == "open"
        ][:3] or ["Confirm objectives and next steps with the client."]

    return AccountBrief(
        account={
            "id": acc.id,
            "name": acc.name,
            "type": acc.type,
            "tier": acc.tier,
            "status": acc.status,
            "aum_with_cg_mm": acc.aum_with_cg_mm,
            "primary_strategy": acc.primary_strategy,
            "relationship_manager": acc.relationship_manager,
            "consultant": acc.consultant,
        },
        meeting=_derive_meeting(acc, opps, now),
        headline=headline,
        risk_flags=flags,
        talking_points=tps,
        since_last_meeting=_since_last_meeting(meetings),
        suggested_next_steps=next_steps,
        meta={
            "generated_at": now.isoformat(),
            "provider": "openrouter",
            "model": config.OPENROUTER_MODEL,
            "grounded_in": ["Capital_Group_CRM_mock.xlsx", "meeting-fixtures"],
        },
    )
