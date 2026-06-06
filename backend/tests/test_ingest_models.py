from datetime import date

from app.ingest.models import FetchedDoc, InstitutionFacts, SourceDescriptor
from app.provenance import Provenance


def test_fetcheddoc_roundtrips_text_and_bytes():
    doc = FetchedDoc.from_text(
        "https://x.gov/a", date(2026, 6, 1), "text/html", "<p>hi 75%</p>"
    )
    assert doc.text() == "<p>hi 75%</p>"
    assert doc.raw() == b"<p>hi 75%</p>"
    raw = FetchedDoc.from_bytes(
        "https://x.gov/b", date(2026, 6, 1), "application/pdf", b"%PDF-1.4"
    )
    assert raw.raw() == b"%PDF-1.4"


def test_source_descriptor_holds_routing():
    sd = SourceDescriptor(
        client_id="CALPERS",
        fact_group="institution",
        extractor="publicplans",
        url="https://publicplansdata.org/api/calpers",
    )
    assert sd.extractor == "publicplans"
    assert sd.query is None


def test_institution_facts_carry_provenance():
    f = InstitutionFacts(
        funded_ratio=0.75, provenance=Provenance(kind="public", url="https://x")
    )
    assert f.funded_ratio == 0.75
    assert f.plan_assets_mm is None
    assert f.provenance.kind == "public"
