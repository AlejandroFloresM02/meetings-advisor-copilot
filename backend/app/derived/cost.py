"""Cost-effectiveness in CEM terms: net value added vs excess cost (spec §6G).

net value added = the mandate's net-of-fee excess return (bps).
excess cost      = the mandate fee minus the peer-median fee (bps), when peers exist.
"""

from __future__ import annotations

from app.derived.peers import peer_median
from app.domain.models import CostEffectiveness


def compute_cost_effectiveness(snap, repo) -> CostEffectiveness:
    if not snap.mandates:
        return CostEffectiveness(
            net_value_added_bps=None,
            excess_cost_bps=None,
            verdict="No CG mandate on record.",
            evidence="",
        )
    m = snap.mandates[0]
    nva = m.net_excess_bps

    # peer-median fee across all mandates in the corpus (same-strategy if available)
    peer_fees = [
        x.fee_bps
        for s in repo.all()
        for x in s.mandates
        if x.fee_bps is not None and x.strategy == m.strategy and x.id != m.id
    ]
    pm = peer_median(peer_fees)
    excess_cost = (
        (m.fee_bps - pm) if (pm is not None and m.fee_bps is not None) else None
    )

    if nva is not None and m.fee_bps is not None:
        verdict = (
            "Adds value net of cost"
            if nva > m.fee_bps
            else "Value-add does not clear the fee"
        )
        evidence = f"Net value added {nva:.0f}bps vs fee {m.fee_bps:.0f}bps" + (
            f"; fee {excess_cost:+.0f}bps vs peer median {pm:.0f}bps."
            if excess_cost is not None
            else " (no peer fee benchmark yet)."
        )
    else:
        verdict = "Insufficient data for a cost-effectiveness verdict."
        evidence = ""
    return CostEffectiveness(
        net_value_added_bps=nva,
        excess_cost_bps=excess_cost,
        verdict=verdict,
        evidence=evidence,
    )
