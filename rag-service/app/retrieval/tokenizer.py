"""
Deterministic tokenization and text preprocessing for BM25 lexical retrieval.

Guarantees:
    - Identical preprocessing applied to documents and search queries.
    - Case normalization (lowercase).
    - Punctuation stripping and word boundary tokenization.
    - Repeated whitespace and empty input safety.
    - No aggressive stemming or lossy lemmatization.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence, Set

# Regex matches alphanumeric sequences (words, numbers, tokens)
_TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)


class BM25Tokenizer:
    """
    Deterministic tokenizer and preprocessor for BM25 lexical indexing and retrieval.

    Args:
        stopwords: Optional collection of words to filter out during tokenization.
                   Defaults to None (all non-empty tokens preserved).
    """

    def __init__(self, stopwords: Optional[Sequence[str] | Set[str]] = None) -> None:
        self.stopwords: set[str] = {w.lower() for w in stopwords} if stopwords else set()

    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize and normalize input text into a deterministic sequence of terms.

        Pipeline:
            1. Handle None / empty / whitespace input safely.
            2. Convert text to lowercase.
            3. Extract word tokens using word boundary regex.
            4. Optionally filter stopwords (if configured).

        Args:
            text: Raw input text string.

        Returns:
            List of normalized string tokens in original occurrence order.
        """
        if not text or not isinstance(text, str):
            return []

        cleaned = text.strip().lower()
        if not cleaned:
            return []

        tokens = _TOKEN_PATTERN.findall(cleaned)

        if self.stopwords:
            tokens = [t for t in tokens if t not in self.stopwords]

        return tokens


# Default shared tokenizer instance
_default_tokenizer = BM25Tokenizer()


def tokenize(text: str) -> list[str]:
    """
    Convenience function using the default deterministic BM25Tokenizer.

    Args:
        text: Raw input text string.

    Returns:
        List of normalized string tokens.
    """
    return _default_tokenizer.tokenize(text)
