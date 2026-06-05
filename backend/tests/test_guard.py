from app.generation.guard import extract_numbers, guard_statements, statement_supported


def test_extract_numbers_strips_punctuation():
    nums = extract_numbers("~$946mm across 2 mandates at 80%")
    assert {"946", "2", "80"} <= nums


def test_unsupported_source_is_dropped():
    valid = {"OPP-3003", "CON-2004"}
    ctx = {"600"}
    assert statement_supported("Advance the $600mm mandate", ["OPP-3003"], valid, ctx)
    assert not statement_supported("Advance it", ["OPP-9999"], valid, ctx)  # bad source
    assert not statement_supported(
        "It is worth $700mm", ["OPP-3003"], valid, ctx
    )  # bad number


def test_guard_filters_list():
    valid = {"OPP-3003"}
    ctx = {"600"}
    stmts = [
        {"text": "$600mm in DD", "sources": ["OPP-3003"]},
        {"text": "$700mm fabricated", "sources": ["OPP-3003"]},
    ]
    kept = guard_statements(stmts, valid, ctx)
    assert len(kept) == 1
    assert kept[0]["text"] == "$600mm in DD"
