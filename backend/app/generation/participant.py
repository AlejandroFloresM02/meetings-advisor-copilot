"""Per-participant card: relationship facts + interests/prior decisions from
meeting fixtures, phrased by the LLM, guarded."""

from __future__ import annotations

from datetime import date

from app.domain.models import ParticipantCard
from app.generation.guard import extract_numbers, statement_supported
from app.generation.prompts import PARTICIPANT_SYSTEM, build_participant_user


def build_participant_card(
    repo, contact_id: str, account_id: str, llm, now: date
) -> ParticipantCard:
    contact = repo.get_contact(contact_id)
    if contact is None:
        raise KeyError(contact_id)
    meetings = repo.meetings_for_account(account_id)
    activities = repo.activities_for_account(account_id)

    interests: list[str] = []
    prior_decisions: list[dict] = []
    meeting_sources: list[str] = []
    for m in meetings:
        if contact_id in m.participants:
            meeting_sources.append(m.id)
            interests.extend(m.participant_interests.get(contact_id, []))
            for d in m.decisions:
                if d.by == contact_id:
                    prior_decisions.append({"text": d.text, "meeting": m.id})
    interests = list(dict.fromkeys(interests))

    recent = [
        {"id": a.id, "date": str(a.date), "subject": a.subject}
        for a in activities
        if a.contact and contact.name and a.contact in contact.name
    ][:3]
    days_since = (now - contact.last_contacted).days if contact.last_contacted else None

    valid = (
        {contact_id, account_id} | {m.id for m in meetings} | {a.id for a in activities}
    )
    ctx_nums = extract_numbers(
        " ".join(interests + [d["text"] for d in prior_decisions])
    )

    facts = {
        "contact": contact.model_dump(),
        "fact_ids": sorted(valid),
        "interests": interests,
        "prior_decisions": prior_decisions,
        "days_since_contact": days_since,
    }
    raw = {}
    try:
        raw = llm.generate_json(PARTICIPANT_SYSTEM, build_participant_user(facts))
    except Exception:
        raw = {}

    relevance = (raw.get("meeting_relevance") or "").strip()
    srcs = raw.get("sources") or [contact_id]
    if relevance and not statement_supported(relevance, srcs, valid, ctx_nums):
        relevance = ""
    if not relevance:
        relevance = f"{contact.role or 'Stakeholder'} at the account" + (
            f"; interests: {', '.join(interests)}." if interests else "."
        )

    talking_point = (raw.get("talking_point") or "").strip()
    if talking_point and not statement_supported(talking_point, srcs, valid, ctx_nums):
        talking_point = ""
    if not talking_point:
        talking_point = (
            f"Acknowledge {contact.name}'s focus on {interests[0]}."
            if interests
            else f"Re-engage {contact.name} ({contact.role or 'contact'})."
        )

    return ParticipantCard(
        contact={
            "id": contact.id,
            "name": contact.name,
            "title": contact.title,
            "role": contact.role,
            "account_id": contact.account_id,
            "last_contacted": contact.last_contacted.isoformat()
            if contact.last_contacted
            else None,
            "email": contact.email,
            "phone": contact.phone,
        },
        relationship={"days_since_contact": days_since, "recent_interactions": recent},
        interests=interests,
        prior_decisions=prior_decisions,
        meeting_relevance=relevance,
        talking_point=talking_point,
        sources=sorted({contact_id, *meeting_sources}),
    )
