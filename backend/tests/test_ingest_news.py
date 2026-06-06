from datetime import date

from app.ingest.extract import news
from app.ingest.models import FetchedDoc

_NEWS_HTML = "<html><body><article>CalPERS placed a small-cap manager on watch.</article></body></html>"


class _StubLlm:
    def extract(self, system: str, user: str) -> dict:
        assert "action" in system.lower()
        return {
            "actions": [
                {
                    "id": "ACT-1",
                    "date": "2026-05-12",
                    "kind": "watch",
                    "manager": "A small-cap equity manager",
                    "asset_class": "Global Equity",
                    "detail": "Placed on watch after underperformance.",
                }
            ]
        }


def test_news_extract_builds_actions_with_provenance():
    doc = FetchedDoc.from_text(
        "https://www.pionline.com/calpers-watch",
        date(2026, 6, 1),
        "text/html",
        _NEWS_HTML,
    )
    actions = news.extract(doc, _StubLlm())
    assert len(actions) == 1
    assert actions[0].kind == "watch"
    assert actions[0].date == date(2026, 5, 12)
    assert actions[0].provenance.kind == "public"
    assert actions[0].provenance.url.endswith("/calpers-watch")
