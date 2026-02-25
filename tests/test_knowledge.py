"""Tests for in-memory knowledge search."""

from ff_agent.knowledge import (
    _tokenize,
    _split_markdown_sections,
    _infer_category,
    search_knowledge,
    reload_knowledge,
)


def test_tokenize_english():
    tokens = _tokenize("Hello World 123")
    assert tokens == ["hello", "world", "123"]


def test_tokenize_chinese():
    tokens = _tokenize("你好世界")
    assert len(tokens) > 0


def test_tokenize_mixed():
    tokens = _tokenize("Hello 你好 World")
    assert "hello" in tokens
    assert "world" in tokens


def test_split_markdown_short():
    text = "# Title\nSome content here that is long enough to be kept."
    chunks = _split_markdown_sections(text)
    assert len(chunks) >= 1
    assert "Title" in chunks[0]


def test_split_markdown_filters_short():
    text = "# H\nTiny"
    chunks = _split_markdown_sections(text)
    assert len(chunks) == 0  # Both too short (< 20 chars)


def test_infer_category():
    assert _infer_category("BrandStory.md") == "brand"
    assert _infer_category("FAQ.md") == "faq"
    assert _infer_category("HowtoUse&Care.md") == "policy"
    assert _infer_category("ProductKnowledge.md") == "general"


def test_reload_knowledge():
    count = reload_knowledge()
    assert count > 0  # Should load from knowledge/ directory


def test_search_returns_results():
    reload_knowledge()
    results = search_knowledge("shipping")
    assert len(results) > 0
    # Should contain shipping-related content
    combined = " ".join(results).lower()
    assert "ship" in combined or "deliver" in combined


def test_search_with_category():
    reload_knowledge()
    results = search_knowledge("brand story", category="brand")
    assert len(results) > 0


def test_search_nonexistent_category():
    reload_knowledge()
    results = search_knowledge("test", category="nonexistent")
    assert len(results) == 1
    assert "No knowledge found" in results[0]


def test_search_empty_query():
    reload_knowledge()
    results = search_knowledge("")
    assert len(results) > 0  # Returns fallback results
