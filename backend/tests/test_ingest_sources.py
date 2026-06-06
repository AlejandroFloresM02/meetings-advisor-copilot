import pytest

from app.ingest.sources import client_identity, sources_for


def test_client_identity_for_calpers():
    ident = client_identity("CALPERS")
    assert ident["name"] == "CalPERS"
    assert ident["type"] == "public_pension"


def test_sources_cover_the_three_public_fact_groups():
    sources = sources_for("CALPERS")
    groups = {s.fact_group for s in sources}
    assert {"institution", "seats", "actions"} <= groups
    extractors = {s.extractor for s in sources}
    assert {"publicplans", "acfr", "board", "news"} <= extractors
    # every descriptor is reachable: it has a canonical URL or a discover query
    assert all(s.url or s.query for s in sources)


def test_unknown_client_raises():
    with pytest.raises(KeyError):
        client_identity("NOPE")
