"""
Token counting abstraction for the embedding service.

Purpose:
    Estimate or accurately measure the number of tokens in a text string
    before sending it to an embedding provider. This prevents the service
    from unknowingly dispatching over-limit requests.

Design:
    A ``TokenCounter`` Protocol defines the interface.  Two implementations
    are provided:

    CharApproxTokenCounter (default, zero dependencies)
        A fast heuristic: tokens ≈ characters / 4.
        Suitable for development, testing, and environments where tiktoken
        is not installed.  Errs on the side of over-counting (conservative),
        which means it may occasionally reject text that the provider would
        actually accept, but it will never silently send over-limit text.

    TiktokenCounter (optional, requires ``tiktoken`` package)
        Uses the tiktoken BPE tokeniser for accurate token counting matching
        OpenAI's own tokenisation.  Automatically selected when available if
        ``auto=True`` is passed to ``make_token_counter()``.

Usage:
    # Auto-select the best available counter for a given model:
    counter = make_token_counter("text-embedding-3-small")
    count = counter.count("Hello, world!")

    # Force the approximation regardless of tiktoken availability:
    counter = make_token_counter(auto=False)
    count = counter.count("Hello, world!")

Important:
    The configured ``EMBEDDING_MAX_TOKENS`` must reflect the token limit of
    the actual embedding model, not the token counter implementation.
    If you switch from ``CharApproxTokenCounter`` to ``TiktokenCounter``
    you may wish to lower the safety margin in your configured limit.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class TokenCounter(Protocol):
    """
    Protocol for token counting strategies.

    Any callable object that implements ``count(text: str) -> int``
    satisfies this protocol.
    """

    def count(self, text: str) -> int:
        """
        Return the token count for ``text``.

        Args:
            text: Input string.  May be empty (returns 0).

        Returns:
            Non-negative integer token count.
        """
        ...  # pragma: no cover


class CharApproxTokenCounter:
    """
    Fast approximation: token count ≈ character count / 4.

    Rationale:
        OpenAI documents that 1 token ≈ 4 characters of English text on
        average.  This approximation is fast, has zero dependencies, and
        errs on the side of over-counting (conservative), which is the
        safe direction for a token-limit guard.

    Accuracy:
        Typically within ±20–25% for standard English prose.
        May under-count for dense code, URLs, or non-Latin scripts.
        For production accuracy, prefer ``TiktokenCounter``.

    Args:
        chars_per_token: Characters-per-token ratio (default 4).
                         Lower values → more conservative (higher estimate).
    """

    def __init__(self, chars_per_token: int = 4) -> None:
        if chars_per_token < 1:
            raise ValueError("chars_per_token must be at least 1")
        self._chars_per_token = chars_per_token

    def count(self, text: str) -> int:
        """
        Return the estimated token count for ``text``.

        Args:
            text: Input string.

        Returns:
            Estimated number of tokens (ceiling division by chars_per_token).
        """
        if not text:
            return 0
        # Ceiling division: conservative (errs high)
        return (len(text) + self._chars_per_token - 1) // self._chars_per_token


class TiktokenCounter:
    """
    Accurate token counter using the ``tiktoken`` BPE tokeniser.

    Requires the optional ``tiktoken`` package to be installed:
        pip install tiktoken

    Uses the tokenizer encoding for the specified model, falling back to
    ``cl100k_base`` (used by text-embedding-3-* and ada-002) if the model
    is not directly recognised by tiktoken.

    Args:
        model: OpenAI model name (e.g. ``"text-embedding-3-small"``).

    Raises:
        ImportError: If ``tiktoken`` is not installed.
    """

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        try:
            import tiktoken  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "tiktoken is required for TiktokenCounter. "
                "Install it with: pip install tiktoken"
            ) from exc

        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base for unknown models
            logger.warning(
                "tiktoken: model '%s' not found; falling back to cl100k_base encoding",
                model,
            )
            self._enc = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        """
        Return the exact BPE token count for ``text``.

        Args:
            text: Input string.

        Returns:
            Exact number of BPE tokens.
        """
        if not text:
            return 0
        return len(self._enc.encode(text))


def make_token_counter(
    model: str = "text-embedding-3-small",
    *,
    auto: bool = True,
) -> TokenCounter:
    """
    Factory that returns the best available token counter.

    If ``auto=True`` (default), attempts to construct a ``TiktokenCounter``
    for accurate counting.  Falls back to ``CharApproxTokenCounter`` if
    ``tiktoken`` is not installed, logging a single info message.

    If ``auto=False``, always returns ``CharApproxTokenCounter``.

    Args:
        model: Embedding model name, forwarded to ``TiktokenCounter``.
        auto:  Whether to attempt tiktoken before falling back.

    Returns:
        A ``TokenCounter`` instance.
    """
    if auto:
        try:
            counter = TiktokenCounter(model=model)
            logger.info(
                "Token counter: using TiktokenCounter for model '%s'", model
            )
            return counter
        except ImportError:
            logger.info(
                "tiktoken not installed — using CharApproxTokenCounter "
                "(characters / 4 heuristic). Install tiktoken for accurate counts."
            )
    return CharApproxTokenCounter()
