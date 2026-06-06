from pathlib import Path

from app.data.snapshot import load_all_snapshots, load_snapshot

SNAP_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshots"


def test_calpers_snapshot_loads_typed():
    snap = load_snapshot(SNAP_DIR / "CALPERS.json")
    assert snap.client_id == "CALPERS"
    assert snap.institution.name == "CalPERS"
    assert snap.institution.funded_ratio == 0.75
    assert snap.institution.provenance.kind == "public"
    # synthetic layer present and tagged
    mandate = snap.mandates[0]
    assert mandate.fee_bps == 38.0
    assert mandate.provenance.kind == "synthetic"
    # the upcoming meeting drives scenario
    assert snap.meetings[0].scenario == "portfolio_review"
    # personas are synthetic over real seats
    person = snap.people[0]
    assert person.provenance.kind == "synthetic"
    assert any(s.id == person.seat_id for s in snap.seats)


def test_load_all_snapshots_indexes_by_client():
    snaps = load_all_snapshots(SNAP_DIR)
    assert "CALPERS" in snaps
