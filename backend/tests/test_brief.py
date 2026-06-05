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


def test_brief_guards_headline_for_fabricated_numbers(repo):
    from tests.conftest import StubLLM
    # A headline citing a number absent from the grounded context is unsupported
    # and must be replaced by the deterministic template fallback.
    bad = build_account_brief(
        repo, "ACC-1002",
        StubLLM({"headline": "Account holds $99999mm in fabricated AUM."}),
        date(2026, 6, 4),
    )
    assert "99999" not in bad.headline
    assert "top risk:" in bad.headline                     # template fallback marker

    # A clean headline (no fabricated numbers) survives the guard verbatim.
    good = build_account_brief(
        repo, "ACC-1002",
        StubLLM({"headline": "Two late-stage mandates in play."}),
        date(2026, 6, 4),
    )
    assert good.headline == "Two late-stage mandates in play."
