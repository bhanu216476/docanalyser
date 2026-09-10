"""
Embedding service exception hierarchy.

Exception strategy:

    EmbeddingError                  — base class for all embedding exceptions
        EmbeddingValidationError    — invalid input (empty text, bad config)
        EmbeddingTokenLimitError    — text exceeds the configured token maximum
        EmbeddingProviderError      — provider returned an unexpected / invalid response
        EmbeddingRetryExhaustedError — transient failures exhausted all retry attempts

Classification:

    ┌───────────────────────────────────────┬───────────┬──────────┐
    │ Exception                             │ Retryable │ Source   │
    ├───────────────────────────────────────┼───────────┼──────────┤
    │ EmbeddingValidationError              │ No        │ input    │
    │ EmbeddingTokenLimitError              │ No        │ input    │
    │ EmbeddingProviderError                │ Depends   │ provider │
    │ EmbeddingRetryExhaustedError          │ No        │ service  │
    └───────────────────────────────────────┴───────────┴──────────┘
"""

from __future__ import annotations


class EmbeddingError(Exception):
    """
    Base class for all embedding service exceptions.

    Catch this to handle any embedding failure without caring about
    the specific sub-type.
    """


class EmbeddingValidationError(EmbeddingError):
    """
    Raised when input fails validation before any provider call is made.

    Examples:
        - Empty or whitespace-only text in a chunk
        - Batch size configured as zero or negative
        - Retry count configured as negative

    This error is NEVER retried — it represents a logical error in the
    caller or configuration that cannot self-correct.
    """


class EmbeddingTokenLimitError(EmbeddingError):
    """
    Raised when one or more input texts exceed the configured token limit.

    The error message identifies the offending chunk by index, the
    measured token count, and the configured maximum — without logging
    the full chunk content.

    This error is NEVER retried — sending the same over-limit text
    again will always fail.

    Attributes:
        chunk_index:  0-based index of the offending input in the batch.
        token_count:  Measured / estimated token count for that input.
        max_tokens:   Configured maximum allowed tokens.
    """

    def __init__(self, chunk_index: int, token_count: int, max_tokens: int) -> None:
        self.chunk_index = chunk_index
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            f"Input at index {chunk_index} exceeds token limit: "
            f"{token_count} tokens > {max_tokens} maximum. "
            f"Split the text into smaller chunks before embedding."
        )


class EmbeddingProviderError(EmbeddingError):
    """
    Raised when the embedding provider returns an invalid or unexpected response.

    Examples:
        - Provider returns fewer vectors than requested
        - Provider returns malformed (non-list, wrong type) embeddings
        - Provider authentication or authorisation failure (permanent)
        - Provider rate-limit or timeout (transient — caught by retry logic)

    The ``is_transient`` flag allows the retry layer to decide whether to
    retry the batch.

    Attributes:
        is_transient: True when the failure is likely temporary (rate limit,
                      network error, 503). False for permanent failures
                      (auth, bad request).
    """

    def __init__(self, message: str, *, is_transient: bool = False) -> None:
        self.is_transient = is_transient
        super().__init__(message)


class EmbeddingRetryExhaustedError(EmbeddingError):
    """
    Raised when all retry attempts for a transient provider failure have
    been exhausted without a successful response.

    Attributes:
        attempts:    Total number of attempts made (including the first).
        batch_index: 0-based index of the failing batch within the overall
                     request, useful for debugging which part of the input
                     caused the issue.
        cause:       The last underlying exception that triggered the final
                     retry failure.
    """

    def __init__(
        self,
        attempts: int,
        batch_index: int,
        cause: Exception,
    ) -> None:
        self.attempts = attempts
        self.batch_index = batch_index
        self.cause = cause
        super().__init__(
            f"Embedding provider failed after {attempts} attempt(s) "
            f"on batch {batch_index}. Last error: {cause}"
        )
