"""Fact-check guard: a statement survives only if every source is valid and
every number it states appears in the grounded context."""

from __future__ import annotations

import re

_NUM = re.compile(r"\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.findall(text or ""):
        out.add(m)
        if "." in m:  # also index the integer part ("946.0" -> "946")
            out.add(m.split(".")[0])
    return out


def _expand(numbers: set[str]) -> set[str]:
    out = set(numbers)
    for n in numbers:
        if "." in n:
            out.add(n.split(".")[0])
    return out


def statement_supported(
    text, sources, valid_sources: set[str], context_numbers: set[str]
) -> bool:
    if sources and not all(s in valid_sources for s in sources):
        return False
    nums = extract_numbers(text)
    return not nums or nums <= _expand(context_numbers)


def guard_statements(
    statements: list[dict], valid_sources: set[str], context_numbers: set[str]
) -> list[dict]:
    kept = []
    for s in statements:
        text = (s.get("text") or "").strip()
        if text and statement_supported(
            text, s.get("sources", []), valid_sources, context_numbers
        ):
            kept.append({"text": text, "sources": s.get("sources", [])})
    return kept
