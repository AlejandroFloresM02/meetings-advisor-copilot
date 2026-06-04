from __future__ import annotations


def percentile_rank(values: list[float], value: float) -> float:
    """Fraction of `values` <= `value` (0..1). Empty -> 0.5."""
    if not values:
        return 0.5
    return sum(1 for v in values if v <= value) / len(values)
