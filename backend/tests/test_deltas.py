from app.derived.deltas import compute_deltas


def test_deltas_detect_funded_ratio_move(calpers):
    prev = calpers.model_copy(deep=True)
    prev.institution.funded_ratio = 0.72
    deltas = compute_deltas(prev, calpers)  # 0.72 -> 0.75
    funded = next(d for d in deltas if d.field == "funded_ratio")
    assert funded.direction == "up"
    assert "72" in funded.summary
    assert "75" in funded.summary


def test_deltas_detect_new_actions(calpers):
    prev = calpers.model_copy(deep=True)
    prev.actions = []  # all current actions are "new"
    deltas = compute_deltas(prev, calpers)
    assert any(d.field == "actions" and d.direction == "changed" for d in deltas)
