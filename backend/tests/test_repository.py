def test_repository_serves_snapshot(repo):
    snap = repo.get("CALPERS")
    assert snap is not None
    assert snap.institution.name == "CalPERS"
    assert repo.get("NOPE") is None


def test_repository_lists_institutions(repo):
    insts = repo.institutions()
    assert any(i.id == "CALPERS" for i in insts)
    assert len(repo.all()) >= 1
