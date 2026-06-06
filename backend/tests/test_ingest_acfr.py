from datetime import date

from app.ingest.extract import acfr
from app.ingest.models import FetchedDoc

_ACFR_TEXT = (
    "CalPERS ACFR FY2025. The funded ratio was 75 percent against a discount "
    "rate of 6.8 percent. Fixed Income target 30%, actual 28%."
)


class _StubLlm:
    """Returns what a model would extract from the ACFR text."""

    def extract(self, system: str, user: str) -> dict:
        assert "funded" in system.lower()  # the prompt asks for funded status
        return {
            "funded_ratio": 0.75,
            "assumed_return": 0.068,
            "fiscal_year": 2025,
            "allocation": [
                {"asset_class": "Fixed Income", "target_pct": 30.0, "actual_pct": 28.0}
            ],
        }


def test_acfr_extract_maps_llm_output_with_provenance():
    doc = FetchedDoc.from_text(
        "https://www.calpers.ca.gov/acfr-2025",
        date(2026, 6, 1),
        "text/plain",
        _ACFR_TEXT,
    )
    facts = acfr.extract(doc, _StubLlm())
    assert facts.funded_ratio == 0.75
    assert facts.assumed_return == 0.068
    assert facts.fiscal_year == 2025
    assert facts.allocation[0].asset_class == "Fixed Income"
    assert facts.provenance.kind == "public"
    assert facts.provenance.url.endswith("acfr-2025")


def test_pdf_to_text_passes_through_non_pdf():
    # For text content the extractor must not invoke pypdf.
    doc = FetchedDoc.from_text("https://x", date(2026, 6, 1), "text/plain", "hello")
    assert acfr._content_text(doc) == "hello"
