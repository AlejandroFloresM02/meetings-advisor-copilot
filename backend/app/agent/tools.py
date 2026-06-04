"""Grounded tools for the ReAct agent. Configure once with repo + llm, then the
tools render the same builders as the REST endpoints into chat-ready markdown."""
from __future__ import annotations

from datetime import date

from langchain_core.tools import tool

from app.generation.brief import build_account_brief
from app.generation.participant import build_participant_card

_STATE: dict = {"repo": None, "llm": None, "now": None}


def configure(repo, llm, now: date) -> None:
    _STATE.update(repo=repo, llm=llm, now=now)


def _resolve_account_id(query: str) -> str | None:
    repo = _STATE["repo"]
    if repo.get_account(query):
        return query
    a = repo.find_account(query)
    return a.id if a else None


def brief_to_md(b) -> str:
    lines = [f"**{b.account['name']}** - {b.headline}", ""]
    lines.append(f"_Snapshot:_ {b.account.get('tier')} / {b.account.get('status')} / "
                 f"${b.account.get('aum_with_cg_mm'):.0f}mm AUM / consultant {b.account.get('consultant')}")
    lines.append("\n**Risk flags:**")
    for f in b.risk_flags:
        ex = f" - {f.explanation}" if f.explanation else ""
        lines.append(f"- [{f.severity.upper()}] {f.title}: {f.evidence}{ex}")
    lines.append("\n**Talking points:**")
    for t in b.talking_points:
        lines.append(f"- {t.text}")
    if b.suggested_next_steps:
        lines.append("\n**Next steps:** " + "; ".join(b.suggested_next_steps))
    return "\n".join(lines)


@tool
def get_account_brief(account: str) -> str:
    """Generate the pre-meeting brief for an account by ID (ACC-1002) or name (Calderon)."""
    aid = _resolve_account_id(account)
    if not aid:
        return f"No account found matching '{account}'."
    b = build_account_brief(_STATE["repo"], aid, _STATE["llm"], _STATE["now"])
    return brief_to_md(b)


@tool
def get_participant_card(name_or_id: str, account: str) -> str:
    """Profile a meeting participant (by contact name or ID) for a given account."""
    repo = _STATE["repo"]
    aid = _resolve_account_id(account)
    contact = repo.get_contact(name_or_id) or repo.find_contact(name_or_id)
    if not contact or not aid:
        return f"No participant '{name_or_id}' found for account '{account}'."
    c = build_participant_card(repo, contact.id, aid, _STATE["llm"], _STATE["now"])
    rel = (f"last contacted {c.relationship['days_since_contact']}d ago"
           if c.relationship.get("days_since_contact") is not None else "")
    return (f"**{c.contact['name']}** - {c.contact['title']} ({c.contact['role']}). {rel}\n"
            f"{c.meeting_relevance}\nInterests: {', '.join(c.interests) or 'n/a'}\n"
            f"Talking point: {c.talking_point}")


@tool
def list_today_meetings() -> str:
    """List the accounts with upcoming meetings (the Today's Meetings list)."""
    repo = _STATE["repo"]
    rows = [f"- {a.id} {a.name} ({a.status}, {a.tier})" for a in repo.list_accounts()]
    return "Accounts:\n" + "\n".join(rows[:25])


@tool
def get_meeting_history(account: str) -> str:
    """Summaries of prior (synthetic) meetings for an account."""
    aid = _resolve_account_id(account)
    if not aid:
        return f"No account matching '{account}'."
    ms = _STATE["repo"].meetings_for_account(aid)
    if not ms:
        return "No prior meetings on record."
    return "\n".join(f"- {m.date} {m.title}: {m.summary}" for m in ms)


TOOLS = [get_account_brief, get_participant_card, list_today_meetings, get_meeting_history]
