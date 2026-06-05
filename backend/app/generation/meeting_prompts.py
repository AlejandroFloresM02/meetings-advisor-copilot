"""Prompt for synthesizing a single prior meeting from a real Activity seed."""

from __future__ import annotations

import json

MEETING_SYSTEM = (
    "You generate a realistic but SYNTHETIC record of a PAST institutional client "
    "meeting for a mock CRM demo. Stay consistent with the provided facts (account, "
    "contacts, open mandates). Do not contradict them. Reference people by their real "
    'names from the contacts list. Return JSON: {"summary": str, '
    '"decisions": [{"text": str, "by": contact_name}], '
    '"action_items": [{"text": str, "owner": str, "status": "open"|"done"}], '
    '"participant_interests": {contact_name: [str]}, '
    '"transcript_excerpt": [{"speaker": contact_name, "text": str}], '
    '"participants": [contact_name]}.'
)


def build_meeting_user(seed: dict) -> str:
    return "SEED FACTS (JSON):\n" + json.dumps(seed, indent=2, default=str)
