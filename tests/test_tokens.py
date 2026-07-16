from code_analyzer.tokens import count_tokens, fits_budget, split_to_budget


def test_count_tokens_monotonic():
    assert count_tokens("") == 0
    assert count_tokens("hello world") > 0
    assert count_tokens("a" * 1000) > count_tokens("a" * 10)


def test_split_returns_single_chunk_when_small():
    text = "line1\nline2\n"
    assert split_to_budget(text, budget=10_000) == [text]


def test_split_respects_budget():
    text = "\n".join(f"public void method{i}() {{ return; }}" for i in range(500))
    chunks = split_to_budget(text, budget=50)
    assert len(chunks) > 1
    for c in chunks:
        # Each chunk should be at or near the budget (allow the boundary line).
        assert fits_budget(c, budget=120)
    # Reassembling chunks reproduces the original content.
    assert "".join(chunks) == text


def test_hard_split_of_giant_single_line():
    giant = "x" * 100_000  # one line, no newlines
    chunks = split_to_budget(giant, budget=100)
    assert len(chunks) > 1
    assert "".join(chunks) == giant
