from datetime import date

from app.ingest.extract import board
from app.ingest.models import FetchedDoc

_BOARD_HTML = """
<html><body>
<h1>Investment Committee</h1>
<div class="seat"><h3>Chief Investment Officer</h3><p>Leads the total fund.</p></div>
<script>ignore me</script>
</body></html>
"""


class _StubLlm:
    def extract(self, system: str, user: str) -> dict:
        assert "seat" in system.lower()
        assert "ignore me" not in user  # script text stripped before the prompt
        return {
            "seats": [
                {
                    "id": "SEAT-CIO",
                    "title": "Chief Investment Officer",
                    "remit": "Total fund",
                    "committee": "Investment Committee",
                    "decides": "Manager retention & allocation",
                    "priorities": ["cost-efficiency", "total-fund risk"],
                }
            ]
        }


def test_board_extract_builds_seats_with_provenance():
    doc = FetchedDoc.from_text(
        "https://www.calpers.ca.gov/about/board",
        date(2026, 6, 1),
        "text/html",
        _BOARD_HTML,
    )
    seats = board.extract(doc, _StubLlm())
    assert len(seats) == 1
    assert seats[0].id == "SEAT-CIO"
    assert seats[0].title == "Chief Investment Officer"
    assert "cost-efficiency" in seats[0].priorities
    assert seats[0].provenance.kind == "public"
    assert seats[0].provenance.url.endswith("/about/board")


def test_html_to_text_strips_scripts():
    assert "ignore me" not in board.html_to_text(_BOARD_HTML)
    assert "Chief Investment Officer" in board.html_to_text(_BOARD_HTML)
