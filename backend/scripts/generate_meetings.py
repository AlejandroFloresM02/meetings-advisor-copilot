r"""Offline: synthesize prior-meeting fixtures with local Ollama, seeded from real
Activities. Validates to MeetingRecord and writes data/generated/meetings/<ACC>.json.

Run:  .\.venv\Scripts\python.exe scripts\generate_meetings.py [ACC-1002 ACC-1017 ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app import config
from app.data.repository import Repository, load_repository
from app.domain.models import (
    ActionItem,
    Activity,
    Decision,
    MeetingRecord,
    TranscriptTurn,
)
from app.generation.meeting_prompts import MEETING_SYSTEM, build_meeting_user

MEETING_TYPES = {"Meeting", "Call", "Portfolio Review", "Conference"}


def _name_to_id(contacts) -> dict[str, str]:
    return {c.name: c.id for c in contacts}


def build_meeting_record(
    activity: Activity, account, contacts, raw: dict, index: int
) -> MeetingRecord:
    n2i = _name_to_id(contacts)
    valid_ids = set(n2i.values())

    def to_id(name):
        return n2i.get(name) or (name if name in valid_ids else None)

    participants = [
        pid for pid in (to_id(p) for p in raw.get("participants", [])) if pid
    ]
    if not participants and activity.contact:
        pid = to_id(activity.contact)
        if pid:
            participants = [pid]

    interests = {}
    for name, items in (raw.get("participant_interests") or {}).items():
        cid = to_id(name)
        if cid and isinstance(items, list):
            interests[cid] = [str(x) for x in items]

    decisions = [
        Decision(text=d.get("text", ""), by=to_id(d.get("by")))
        for d in (raw.get("decisions") or [])
        if d.get("text")
    ]
    action_items = [
        ActionItem(
            text=a.get("text", ""), owner=a.get("owner"), status=a.get("status", "open")
        )
        for a in (raw.get("action_items") or [])
        if a.get("text")
    ]
    transcript = [
        TranscriptTurn(speaker=t.get("speaker", "?"), text=t.get("text", ""))
        for t in (raw.get("transcript_excerpt") or [])
        if t.get("text")
    ]

    acc_num = account.id.split("-")[-1]
    return MeetingRecord(
        id=f"MTG-{acc_num}-{index:02d}",
        date=activity.date or config.NOW,
        type=activity.type,
        title=activity.subject or "Client meeting",
        participants=participants,
        summary=raw.get("summary", "").strip(),
        decisions=decisions,
        action_items=action_items,
        participant_interests=interests,
        transcript_excerpt=transcript,
        source_activity=activity.id,
        synthetic=True,
    )


def generate_for_account(repo: Repository, account_id: str, llm) -> dict:
    account = repo.get_account(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    seeds = [
        a
        for a in repo.activities_for_account(account_id)
        if (a.type or "") in MEETING_TYPES
    ]
    meetings = []
    for i, act in enumerate(seeds, start=1):
        seed = {
            "account": {
                "name": account.name,
                "type": account.type,
                "status": account.status,
                "primary_strategy": account.primary_strategy,
                "consultant": account.consultant,
            },
            "contacts": [
                {"name": c.name, "title": c.title, "role": c.role} for c in contacts
            ],
            "open_mandates": [
                {
                    "opportunity": o.opportunity,
                    "strategy": o.strategy,
                    "size_mm": o.mandate_size_mm,
                    "stage": o.stage,
                }
                for o in opps
            ],
            "activity": {
                "date": str(act.date),
                "type": act.type,
                "subject": act.subject,
                "contact": act.contact,
                "next_step": act.next_step,
            },
        }
        try:
            raw = llm.generate_json(MEETING_SYSTEM, build_meeting_user(seed))
        except Exception:
            raw = {}
        meetings.append(
            build_meeting_record(act, account, contacts, raw, i).model_dump(mode="json")
        )
    return {"account_id": account_id, "meetings": meetings}


def main(argv: list[str]) -> None:
    repo = load_repository(config.CRM_XLSX_PATH, config.MEETINGS_DIR)
    from app.llm.ollama_client import OllamaClient

    try:
        llm = OllamaClient()  # default qwen2.5:7b-instruct
    except Exception:
        llm = OllamaClient(model=config.OLLAMA_MODEL_FALLBACK)
    targets = argv or [a.id for a in repo.list_accounts()]
    out_dir = Path(config.MEETINGS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for aid in targets:
        data = generate_for_account(repo, aid, llm)
        (out_dir / f"{aid}.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        print(f"wrote {aid}.json ({len(data['meetings'])} meetings)")


if __name__ == "__main__":
    main(sys.argv[1:])
