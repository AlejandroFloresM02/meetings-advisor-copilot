from app.derived.cost import compute_cost_effectiveness
from app.derived.peers import peer_median, percentile_rank


def test_percentile_and_median():
    assert percentile_rank([10, 20, 30, 40], 30) == 0.75
    assert percentile_rank([], 5) == 0.5
    assert peer_median([10, 20, 30]) == 20
    assert peer_median([]) is None


def test_cost_effectiveness_uses_net_value_added(repo, calpers):
    ce = compute_cost_effectiveness(calpers, repo)
    # net value added derives from the mandate's net excess (62bps); fee 38bps
    assert ce.net_value_added_bps == 62.0
    assert "62" in ce.evidence
    assert "38" in ce.evidence
    assert ce.verdict  # non-empty narrative verdict
