"""Provenance-aware fact-check guard (spec §8): a hard groundedness gate, not a
hallucination eliminator. An InsightUnit survives only if every number in its
insight/why_now/play text appears in its evidence (which carries provenance)."""

from __future__ import annotations

import re

_NUM = re.compile(r"\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.findall(text or ""):
        out.add(m)
        if "." in m:
            out.add(m.split(".")[0])  # index integer part too ("946.0" -> "946")
    return out


def evidence_numbers(evidence) -> set[str]:
    nums: set[str] = set()
    for e in evidence:
        nums |= extract_numbers(e.text)
    return nums


def unit_supported(u) -> bool:
    claim_nums = (
        extract_numbers(u.insight)
        | extract_numbers(u.why_now or "")
        | extract_numbers(u.play or "")
    )
    if not claim_nums:
        return bool(u.evidence)  # qualitative claim still needs at least one cited fact
    return bool(u.evidence) and claim_nums <= evidence_numbers(u.evidence)


def guard_units(units) -> list:
    return [u for u in units if unit_supported(u)]
