from datetime import date

from app.generation.brief import build_account_brief


def test_brief_uses_guarded_llm_output(repo):
    from tests.conftest import StubLLM
    llm = StubLLM({
        "headline": "Two late-stage mandates in play.",
        "risk_explanations": {"coverage": "No economic buyer is mapped yet."},
        "talking_points": [
            {"text": "Advance the Bond Fund DD mandate", "sources": ["OPP-3003"]},
            {"text": "Fabricated $999mm claim", "sources": ["OPP-3003"]},  # bad number -> dropped
        ],
        "next_steps": ["Send Mercer the breakpoint schedule"],
    })
    brief = build_account_brief(repo, "ACC-1002", llm, date(2026, 6, 4))
    assert brief.headline == "Two late-stage mandates in play."
    texts = [t.text for t in brief.talking_points]
    assert "Advance the Bond Fund DD mandate" in texts
    assert all("999" not in t for t in texts)            # guard dropped the fake number
    assert any(f.id == "coverage" for f in brief.risk_flags)
    assert brief.meta["grounded_in"]


def test_brief_falls_back_when_llm_empty(repo):
    from tests.conftest import StubLLM
    brief = build_account_brief(repo, "ACC-1002", StubLLM({}), date(2026, 6, 4))
    assert brief.headline                                  # template fallback
    assert len(brief.talking_points) >= 1
