"""Period-over-period deltas between two snapshots (spec §5⑤, §9 #3)."""

from __future__ import annotations

from app.domain.models import Delta


def _num_delta(field, before, after) -> Delta | None:
    if before is None or after is None or before == after:
        return None
    direction = "up" if after > before else "down"
    return Delta(
        field=field,
        before=before,
        after=after,
        direction=direction,
        summary=f"{field.replace('_', ' ')} moved {before} → {after}.",
    )


def compute_deltas(prev, curr) -> list[Delta]:
    out: list[Delta] = []
    pi, ci = prev.institution, curr.institution
    for field in ("funded_ratio", "assumed_return", "plan_assets_mm"):
        d = _num_delta(field, getattr(pi, field), getattr(ci, field))
        if d:
            out.append(d)

    # new investment actions since the prior snapshot
    prev_ids = {a.id for a in prev.actions}
    new_actions = [a for a in curr.actions if a.id not in prev_ids]
    if new_actions:
        out.append(
            Delta(
                field="actions",
                before=len(prev.actions),
                after=len(curr.actions),
                direction="changed",
                summary=f"{len(new_actions)} new investment action(s): "
                f"{new_actions[0].detail}",
            )
        )
    return out
