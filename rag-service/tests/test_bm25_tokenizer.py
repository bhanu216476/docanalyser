"""Unit tests for BM25 deterministic tokenizer."""

from __future__ import annotations

import pytest

from app.retrieval.tokenizer import BM25Tokenizer, tokenize


class TestBM25Tokenizer:
    """Test suite for deterministic BM25 tokenization and normalization."""

    def test_lowercase_normalization(self) -> None:
        """Case normalization produces lowercase tokens."""
        text = "Hello WORLD! This IS a TEST."
        tokens = tokenize(text)
        assert tokens == ["hello", "world", "this", "is", "a", "test"]

    def test_punctuation_handling(self) -> None:
        """Punctuation is stripped and words separated properly."""
        text = "casual-leave, sick-leave; and (annual) leave... right?"
        tokens = tokenize(text)
        assert tokens == ["casual", "leave", "sick", "leave", "and", "annual", "leave", "right"]

    def test_repeated_whitespace(self) -> None:
        """Repeated whitespace, tabs, and newlines are collapsed cleanly."""
        text = "  How    many \t\t casual \n\n leave   days?  "
        tokens = tokenize(text)
        assert tokens == ["how", "many", "casual", "leave", "days"]

    def test_empty_and_whitespace_only(self) -> None:
        """Empty or whitespace-only inputs return empty token lists."""
        assert tokenize("") == []
        assert tokenize("   ") == []
        assert tokenize("\t\n") == []
        assert tokenize(None) == []  # type: ignore[arg-type]

    def test_alphanumeric_and_numbers(self) -> None:
        """Numbers and alphanumeric identifiers are preserved."""
        text = "Section 12.3: Policy HR-2024 requires 15 days."
        tokens = tokenize(text)
        assert "section" in tokens
        assert "12" in tokens
        assert "3" in tokens
        assert "policy" in tokens
        assert "hr" in tokens
        assert "2024" in tokens
        assert "15" in tokens

    def test_repeated_terms_preserved_in_order(self) -> None:
        """Repeated tokens maintain position and count for TF calculation."""
        text = "leave leave leave policy leave"
        tokens = tokenize(text)
        assert tokens == ["leave", "leave", "leave", "policy", "leave"]
        assert len(tokens) == 5

    def test_custom_stopwords(self) -> None:
        """Configurable stopwords are excluded when supplied."""
        tokenizer = BM25Tokenizer(stopwords=["and", "the", "is"])
        tokens = tokenizer.tokenize("The annual leave and sick leave is approved")
        assert tokens == ["annual", "leave", "sick", "leave", "approved"]
