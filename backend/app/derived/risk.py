"""Deterministic risk engine (spec §5⑥). Each component -> RiskFlag(score 0..1,
evidence carrying the raw numbers, derived provenance)."""

from __future__ import annotations

from datetime import date

from app.domain.models import RiskFlag
from app.provenance import Provenance

_DERIVED = Provenance(kind="derived")


def severity_band(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def _flag(key, title, score, evidence) -> RiskFlag:
    score = max(0.0, min(1.0, score))
    return RiskFlag(
        key=key,
        title=title,
        score=score,
        severity=severity_band(score),
        evidence=evidence,
        provenance=_DERIVED,
    )


def compute_risk(snap, repo, now: date) -> list[RiskFlag]:
    inst = snap.institution
    flags: list[RiskFlag] = []

    # funded status: lower funded ratio -> higher risk (1.0 at 60%, 0 at 100%)
    if inst.funded_ratio is not None:
        score = min(1.0, max(0.0, (1.0 - inst.funded_ratio) / 0.4))
        flags.append(
            _flag(
                "funded_status",
                "Funded status",
                score,
                f"Funded ratio {inst.funded_ratio * 100:.0f}% (assumed return "
                f"{(inst.assumed_return or 0) * 100:.1f}%).",
            )
        )

    # allocation gap: largest |target-actual|, weighted toward underfunded targets
    gaps = [
        (a, (a.target_pct or 0) - (a.actual_pct or 0))
        for a in inst.allocation
        if a.target_pct is not None and a.actual_pct is not None
    ]
    if gaps:
        a, gap = max(gaps, key=lambda t: abs(t[1]))
        score = min(1.0, abs(gap) / 5.0)
        verb = "under-allocated" if gap > 0 else "over-allocated"
        flags.append(
            _flag(
                "allocation_gap",
                "Allocation drift",
                score,
                f"{a.asset_class} {verb} by {abs(gap):.1f}pp "
                f"(target {a.target_pct:.1f}% vs actual {a.actual_pct:.1f}%).",
            )
        )

    # manager on watch / terminations in the public actions
    watch = [x for x in snap.actions if x.kind in ("watch", "terminate")]
    if watch:
        flags.append(
            _flag(
                "manager_watch",
                "Manager under review",
                min(1.0, 0.5 + 0.2 * len(watch)),
                f"{len(watch)} manager(s) on watch/terminated; e.g. {watch[0].detail}",
            )
        )

    # stakeholder coverage: how many attending seats lack a mapped person
    upcoming = snap.meetings[0] if snap.meetings else None
    if upcoming:
        mapped = {p.seat_id for p in snap.people}
        missing = [sid for sid in upcoming.seat_ids if sid not in mapped]
        score = 0.7 if missing else 0.2
        flags.append(
            _flag(
                "coverage",
                "Stakeholder coverage",
                score,
                f"{len(missing)} of {len(upcoming.seat_ids)} attending seats unmapped.",
            )
        )

    # recency of last interaction
    dated = [i.date for i in snap.interactions if i.date]
    if dated:
        days = (now - max(dated)).days
        flags.append(
            _flag(
                "recency",
                "Relationship recency",
                min(1.0, max(0.0, (days - 30) / 150)),
                f"Last interaction {days} days ago.",
            )
        )

    # pipeline urgency: nearest expected close
    closes = [(o.expected_close - now).days for o in snap.pipeline if o.expected_close]
    if closes:
        nearest = min(closes)
        score = 0.8 if nearest < 60 else 0.5 if nearest < 120 else 0.3
        flags.append(
            _flag(
                "pipeline",
                "Pipeline urgency",
                score,
                f"Nearest opportunity closes in {nearest} days.",
            )
        )

    # open action items
    open_items = [ai for i in snap.interactions for ai in i.open_action_items]
    if open_items:
        flags.append(
            _flag(
                "open_actions",
                "Open commitments",
                min(1.0, 0.3 + 0.2 * len(open_items)),
                f"{len(open_items)} open action item(s) from prior meetings.",
            )
        )

    flags.sort(key=lambda f: f.score, reverse=True)
    return flags
