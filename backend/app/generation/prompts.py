"""Prompt builders. The model receives ONLY structured facts and must cite IDs."""

from __future__ import annotations

import json

BRIEF_SYSTEM = (
    "You are a Capital Group institutional relationship-management analyst. "
    "You write pre-meeting briefs. Use ONLY the facts provided. Never invent numbers, "
    "names, dates, or claims. Every talking point and risk explanation must cite the "
    "fact id(s) it is based on, drawn from the provided 'fact_ids'. "
    'Return JSON: {"headline": str, "risk_explanations": {component_key: str}, '
    '"talking_points": [{"text": str, "sources": [fact_id]}], "next_steps": [str]}.'
)

PARTICIPANT_SYSTEM = (
    "You are a Capital Group RM analyst writing a one-paragraph profile of a meeting "
    "participant. Use ONLY the facts provided; never invent. Cite fact ids. "
    'Return JSON: {"meeting_relevance": str, "talking_point": str, "sources": [fact_id]}.'
)


def build_brief_user(facts: dict) -> str:
    return "FACTS (JSON):\n" + json.dumps(facts, indent=2, default=str)


def build_participant_user(facts: dict) -> str:
    return "FACTS (JSON):\n" + json.dumps(facts, indent=2, default=str)
