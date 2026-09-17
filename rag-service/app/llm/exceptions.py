"""Domain exceptions for controlled LLM invocation."""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM-layer failures."""


class LLMValidationError(LLMError):
    """Raised for invalid input or client configuration."""


class LLMTokenLimitError(LLMError):
    """Raised when a prompt exceeds the application input-token guard."""

    def __init__(self, token_count: int, max_tokens: int) -> None:
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            f"Prompt exceeds the configured token limit: {token_count} tokens > "
            f"{max_tokens} maximum. Reduce the context before generation."
        )


class LLMProviderError(LLMError):
    """A normalized provider failure, marked retryable when transient."""

    def __init__(self, message: str, *, is_transient: bool = False) -> None:
        self.is_transient = is_transient
        super().__init__(message)


class LLMRetryExhaustedError(LLMError):
    """Raised after all allowed attempts fail transiently."""

    def __init__(self, attempts: int, cause: Exception) -> None:
        self.attempts = attempts
        self.cause = cause
        super().__init__(
            f"LLM provider failed after {attempts} attempt(s). "
            f"Last error type: {type(cause).__name__}"
        )