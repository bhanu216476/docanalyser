"""
Token counting abstractions and budget tracking.

Provides:
- TokenCounter (Protocol): Structural protocol for counting tokens in text.
- TiktokenCounter: Tokenizer using openai's tiktoken if installed, with regex fallback.
- WhitespaceTokenCounter: Deterministic whitespace token counter for offline / testing.
- ExactCharRatioTokenCounter: Deterministic token counter based on characters (e.g. 4 chars/token).
- BudgetTracker: Stateful budget tracker that tracks used tokens including formatting delimiters.
"""

from __future__ import annotations

import re
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TokenCounter(Protocol):
    """Structural protocol satisfied by any token counting implementation."""

    def count(self, text: str) -> int:
        """
        Return the number of tokens in the given text.

        Args:
            text: Text string to tokenize.

        Returns:
            Non-negative integer token count.
        """
        ...


class WhitespaceTokenCounter:
    """
    Deterministic whitespace-and-word token counter.

    Useful for tests, environments without tiktoken, or lightweight operations.
    Counts words split by whitespace, returning 0 for empty strings.
    """

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(text.split())


class DeterministicCharRatioTokenCounter:
    """
    Deterministic token counter based on a fixed character-to-token ratio.

    Useful for testing exact budget boundaries deterministically.
    Default ratio is 4 characters per token (rounding up).
    """

    def __init__(self, chars_per_token: int = 4) -> None:
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self.chars_per_token = chars_per_token

    def count(self, text: str) -> int:
        if not text:
            return 0
        return (len(text) + self.chars_per_token - 1) // self.chars_per_token


class TiktokenCounter:
    """
    BPE token counter using OpenAI's tiktoken library when available.

    If tiktoken is not installed, it falls back to a standardized regex-based
    word/punctuation tokenizer to provide realistic token counts without crashing.
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding_name = encoding_name
        self._encoder = None
        self._tiktoken_available = False

        try:
            import tiktoken  # type: ignore[import-not-found]
            self._encoder = tiktoken.get_encoding(encoding_name)
            self._tiktoken_available = True
        except (ImportError, Exception):
            self._tiktoken_available = False
            self._encoder = None
            # Standard subword/word pattern fallback using Python's standard re module
            self._fallback_pattern = re.compile(
                r"""'s|'t|'re|'ve|'m|'ll|'d|\w+|[^\w\s]""",
                re.UNICODE,
            )

    @property
    def is_tiktoken_available(self) -> bool:
        """Return True if real tiktoken encoding is active."""
        return self._tiktoken_available

    def count(self, text: str) -> int:
        if not text:
            return 0

        if self._tiktoken_available and self._encoder is not None:
            return len(self._encoder.encode(text, disallowed_special=()))

        # Fallback approximation: word tokens + punctuation
        tokens = self._fallback_pattern.findall(text)
        return len(tokens)


class BudgetTracker:
    """
    Helper to track token consumption against a configured budget.

    Maintains current token usage, calculates delimiter overhead,
    and determines whether candidate text will fit within the remaining budget.
    """

    def __init__(
        self,
        token_budget: int,
        token_counter: TokenCounter,
        separator: str = "\n\n",
    ) -> None:
        self.budget = token_budget
        self.counter = token_counter
        self.separator = separator
        self.separator_tokens = token_counter.count(separator) if separator else 0
        self.used_tokens = 0
        self.item_count = 0

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.budget - self.used_tokens)

    def can_fit(self, item_tokens: int) -> bool:
        """
        Check if an item with `item_tokens` can fit in the remaining budget,
        accounting for the separator overhead if not the first item.
        """
        additional_tokens = item_tokens
        if self.item_count > 0:
            additional_tokens += self.separator_tokens

        return (self.used_tokens + additional_tokens) <= self.budget

    def add(self, item_tokens: int) -> None:
        """Record consumption of item_tokens (including separator overhead)."""
        if self.item_count > 0:
            self.used_tokens += self.separator_tokens
        self.used_tokens += item_tokens
        self.item_count += 1
