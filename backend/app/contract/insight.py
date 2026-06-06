"""Deterministic brief assembler (spec §9): snapshot + derived layer -> ranked,
guarded InsightUnits, ordered by meeting scenario. Template/fallback path (no LLM)."""

from __future__ import annotations

from datetime import date

from app.derived.cost import compute_cost_effectiveness
from app.derived.risk import compute_risk
from app.domain.models import Brief, Evidence, InsightUnit
from app.guard import guard_units
from app.provenance import Provenance

DISCLAIMER = (
    "AI-generated brief — always verify before the meeting. Not investment advice."
)

# which sections lead, per scenario (spec §9)
_SCENARIO_ORDER = {
    "portfolio_review": ["risks", "portfolio", "the_room", "next_steps"],
    "finals": ["recommendations", "the_room", "risks", "next_steps"],
    "at_risk_save": ["risks", "portfolio", "the_room", "next_steps"],
    "relationship_review": ["the_room", "portfolio", "risks", "next_steps"],
}


def _ev(text: str, kind: str, url: str | None = None) -> Evidence:
    return Evidence(text=text, provenance=Provenance(kind=kind, url=url))


def _risk_units(snap, repo, now) -> list[InsightUnit]:
    units = []
    for f in compute_risk(snap, repo, now)[:4]:
        units.append(
            InsightUnit(
                insight=f"{f.title}: {f.evidence}",
                why_now=f"Ranked {f.severity} risk for this meeting.",
                evidence=[_ev(f.evidence, "derived")],
                severity=f.severity,
                score=f.score,
                freshness="frozen",
            )
        )
    return units


def _portfolio_units(snap, repo) -> list[InsightUnit]:
    ce = compute_cost_effectiveness(snap, repo)
    if not snap.mandates or ce.net_value_added_bps is None:
        return []
    m = snap.mandates[0]
    return [
        InsightUnit(
            insight=f"{m.strategy}: net excess {m.net_excess_bps:.0f}bps "
            f"at a {m.fee_bps:.0f}bps fee.",
            why_now=ce.verdict + ".",
            evidence=[
                _ev(ce.evidence, "synthetic"),
                _ev(
                    f"Information ratio {m.information_ratio}, "
                    f"down-capture {m.down_capture}.",
                    "synthetic",
                ),
            ],
            play="Lead with after-fee value.",
            freshness="frozen",
        )
    ]


def _room_units(snap) -> list[InsightUnit]:
    seats = {s.id: s for s in snap.seats}
    units = []
    upcoming = snap.meetings[0] if snap.meetings else None
    seat_ids = upcoming.seat_ids if upcoming else list(seats)
    people_by_seat = {p.seat_id: p for p in snap.people}
    for sid in seat_ids:
        seat = seats.get(sid)
        if not seat:
            continue
        person = people_by_seat.get(sid)
        who = f"{person.name} — {seat.title}" if person else seat.title
        priorities = ", ".join(seat.priorities) or "priorities not on record"
        units.append(
            InsightUnit(
                insight=f"{who}: decides {seat.decides or 'n/a'}.",
                why_now=f"Cares about {priorities}.",
                evidence=[
                    _ev(
                        f"{seat.title} priorities: {priorities}.",
                        seat.provenance.kind,
                        seat.provenance.url,
                    )
                ],
                play="Engage on what this seat controls.",
                freshness="frozen",
            )
        )
    return units


def _next_step_units(snap) -> list[InsightUnit]:
    units = []
    for interaction in snap.interactions:
        for ai in interaction.open_action_items:
            units.append(
                InsightUnit(
                    insight=f"Close prior commitment: {ai}.",
                    why_now="Open action item from the last interaction.",
                    evidence=[_ev(ai, "synthetic")],
                    freshness="frozen",
                )
            )
    return units


def build_brief(snap, repo, now: date) -> Brief:
    upcoming = snap.meetings[0] if snap.meetings else None
    scenario = upcoming.scenario if upcoming else "relationship_review"

    sections = {
        "risks": guard_units(_risk_units(snap, repo, now)),
        "portfolio": guard_units(_portfolio_units(snap, repo)),
        "the_room": guard_units(_room_units(snap)),
        "next_steps": guard_units(_next_step_units(snap)),
    }

    top_risk = sections["risks"][0].insight if sections["risks"] else ""
    objective = (
        upcoming.objective if upcoming else None
    ) or f"Relationship review — {snap.institution.name}"
    bluf = f"{objective}. Top risk — {top_risk}" if top_risk else objective

    ordered = {
        k: sections[k]
        for k in _SCENARIO_ORDER.get(scenario, list(sections))
        if sections.get(k)
    }

    return Brief(
        client_id=snap.client_id,
        scenario=scenario,
        bluf=bluf,
        sections=ordered,
        meta={
            "generated_at": now.isoformat(),
            "contains_synthetic": True,
            "disclaimer": DISCLAIMER,
            "grounded_in": ["snapshot", "derived"],
        },
    )
