"""Deterministic risk math. Each component -> (score 0..1, evidence, sources)."""

from __future__ import annotations

from datetime import date

from app.config import RISK_WEIGHTS
from app.domain.models import RiskComponent, RiskResult
from app.risk.peers import percentile_rank


def severity_band(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def _comp(key, title, score, evidence, sources) -> RiskComponent:
    score = max(0.0, min(1.0, score))
    return RiskComponent(
        key=key,
        title=title,
        score=score,
        severity=severity_band(score),
        evidence=evidence,
        sources=sources,
    )


def compute_risk(repo, account_id: str, now: date) -> RiskResult:
    acc = repo.get_account(account_id)
    contacts = repo.contacts_for_account(account_id)
    opps = repo.pipeline_for_account(account_id)
    meetings = repo.meetings_for_account(account_id)
    comps: list[RiskComponent] = []

    # coverage
    roles = [c.role for c in contacts]
    has_dm = any(r == "Decision Maker" for r in roles)
    n = len(contacts)
    if n == 0:
        comps.append(
            _comp("coverage", "Stakeholder coverage", 0.7, "No contacts mapped.", [])
        )
    else:
        breakdown = ", ".join(f"{roles.count(r)} {r}" for r in sorted(set(roles)) if r)
        score = 0.82 if not has_dm else 0.25
        comps.append(
            _comp(
                "coverage",
                "Stakeholder coverage",
                score,
                f"{n} contacts: {breakdown}; {'no Decision Maker mapped' if not has_dm else 'Decision Maker mapped'}.",
                [c.id for c in contacts],
            )
        )

    # recency
    dated = [c for c in contacts if c.last_contacted]
    if dated:
        latest = max(dated, key=lambda c: c.last_contacted)
        days = (now - latest.last_contacted).days
        score = min(1.0, max(0.0, (days - 30) / 150))
        comps.append(
            _comp(
                "recency",
                "Relationship recency",
                score,
                f"Most recent contact {days} days ago ({latest.last_contacted.isoformat()}).",
                [latest.id],
            )
        )
    else:
        comps.append(
            _comp(
                "recency",
                "Relationship recency",
                0.6,
                "No contact dates on record.",
                [],
            )
        )

    # status
    smap = {"At Risk": 0.9, "Prospect": 0.5, "Active": 0.2}
    s = acc.status or ""
    comps.append(
        _comp(
            "status",
            "Account status",
            smap.get(s, 0.3),
            f"Account status: {s or 'unknown'}.",
            [acc.id],
        )
    )

    # aum vs peers
    if (acc.status == "Prospect") or acc.aum_with_cg_mm == 0.0:
        comps.append(
            _comp(
                "aum_vs_peers",
                "AUM vs peers",
                0.4,
                f"${acc.aum_with_cg_mm:.0f}mm current AUM (prospect / conversion).",
                [acc.id],
            )
        )
    else:
        peers = [
            a.aum_with_cg_mm
            for a in repo.list_accounts()
            if a.type == acc.type and a.aum_with_cg_mm > 0 and a.id != acc.id
        ]
        pct = percentile_rank(peers, acc.aum_with_cg_mm)
        comps.append(
            _comp(
                "aum_vs_peers",
                "AUM vs peers",
                1.0 - pct,
                f"${acc.aum_with_cg_mm:.0f}mm = {pct:.0%} percentile among {acc.type} peers.",
                [acc.id],
            )
        )

    # pipeline
    open_opps = [o for o in opps if (o.stage or "") not in ("Won", "Lost")]
    if not open_opps:
        comps.append(
            _comp("pipeline", "Pipeline dynamics", 0.1, "No open pipeline.", [])
        )
    else:
        weighted = sum(o.mandate_size_mm * o.probability for o in open_opps)
        closes = [(o.expected_close - now).days for o in open_opps if o.expected_close]
        nearest = min(closes) if closes else None
        score = (
            0.8
            if (nearest is not None and nearest < 60)
            else 0.5
            if (nearest is not None and nearest < 120)
            else 0.3
        )
        near_txt = (
            f"nearest close in {nearest}d" if nearest is not None else "no close dates"
        )
        comps.append(
            _comp(
                "pipeline",
                "Pipeline dynamics",
                score,
                f"{len(open_opps)} open opps, ${weighted:.0f}mm prob-weighted; {near_txt}.",
                [o.id for o in open_opps],
            )
        )

    # loss history (trailing 12 months)
    lost = [
        o
        for o in opps
        if (o.stage == "Lost")
        and o.expected_close
        and (now - o.expected_close).days <= 365
    ]
    comps.append(
        _comp(
            "loss",
            "Loss history",
            0.6 if lost else 0.1,
            f"{len(lost)} lost opportunity(ies) in the trailing 12 months.",
            [o.id for o in lost],
        )
    )

    # consultant influence
    ext = bool(acc.consultant) and acc.consultant != "In-house"
    comps.append(
        _comp(
            "consultant",
            "Consultant influence",
            0.5 if ext else 0.15,
            f"Consultant: {acc.consultant or 'unknown'}{' (external influence)' if ext else ''}.",
            [acc.id],
        )
    )

    # open action items from prior meetings
    open_items = [
        (m.id, ai) for m in meetings for ai in m.action_items if ai.status == "open"
    ]
    if open_items:
        comps.append(
            _comp(
                "open_actions",
                "Open action items",
                min(1.0, 0.3 + 0.2 * len(open_items)),
                f"{len(open_items)} open action item(s) from prior meetings.",
                sorted({mid for mid, _ in open_items}),
            )
        )
    else:
        comps.append(
            _comp("open_actions", "Open action items", 0.1, "No open action items.", [])
        )

    total_w = sum(RISK_WEIGHTS.get(c.key, 0) for c in comps) or 1.0
    overall = sum(RISK_WEIGHTS.get(c.key, 0) * c.score for c in comps) / total_w
    comps.sort(key=lambda c: c.score, reverse=True)
    return RiskResult(
        overall=overall, severity=severity_band(overall), components=comps
    )
