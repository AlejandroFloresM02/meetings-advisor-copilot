"""Peer-relative helpers (spec §6G). Degenerate-safe for a single-client corpus."""

from __future__ import annotations


def percentile_rank(values: list[float], value: float) -> float:
    """Fraction of values <= value (0..1). Empty -> 0.5."""
    if not values:
        return 0.5
    return sum(1 for v in values if v <= value) / len(values)


def peer_median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
