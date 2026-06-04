from datetime import date

from app.generation.participant import build_participant_card


def test_participant_card_grounded(repo):
    from tests.conftest import StubLLM
    llm = StubLLM({"meeting_relevance": "Gatekeeper controlling committee access.",
                   "talking_point": "Confirm the funding timeline.",
                   "sources": ["CON-2005"]})
    card = build_participant_card(repo, "CON-2005", "ACC-1002", llm, date(2026, 6, 4))
    assert card.contact["id"] == "CON-2005"
    assert card.contact["role"]
    assert "relationship" in card.model_dump()
    assert card.meeting_relevance


def test_participant_card_fallback(repo):
    from tests.conftest import StubLLM
    card = build_participant_card(repo, "CON-2005", "ACC-1002", StubLLM({}), date(2026, 6, 4))
    assert card.meeting_relevance        # falls back to a templated line
