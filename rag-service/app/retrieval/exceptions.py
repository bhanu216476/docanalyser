"""
Dense retrieval exception hierarchy.

Exception strategy:

    RetrievalError                  — base class for all retrieval exceptions
        RetrievalQueryError         — invalid query or top_k (non-retryable)
        RetrievalEmbeddingError     — embedding generation failed
        RetrievalQdrantError        — Qdrant search operation failed

Classification:

    ┌────────────────────────────────────────────┬───────────┬──────────────┐
    │ Exception                                  │ Retryable │ Source       │
    ├────────────────────────────────────────────┼───────────┼──────────────┤
    │ RetrievalQueryError                        │ No        │ caller input │
    │ RetrievalEmbeddingError (is_transient=F)   │ No        │ provider     │
    │ RetrievalEmbeddingError (is_transient=T)   │ Yes       │ provider     │
    │ RetrievalQdrantError (is_transient=F)      │ No        │ Qdrant       │
    │ RetrievalQdrantError (is_transient=T)      │ Yes       │ Qdrant       │
    └────────────────────────────────────────────┴───────────┴──────────────┘

Design principles:
    - Do not expose secrets or credentials in error messages.
    - Distinguish "no results" (empty list) from infrastructure failures.
    - Non-retryable errors propagate immediately without retry.
"""

from __future__ import annotations


class RetrievalError(Exception):
    """Base exception for all retrieval errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class RetrievalQueryError(RetrievalError):
    """
    Raised when query or top_k validation fails.

    Examples:
        - Empty or whitespace-only query
        - top_k is zero or negative
        - top_k exceeds the configured maximum

    Non-retryable. The caller must fix the input before retrying.
    """


class RetrievalEmbeddingError(RetrievalError):
    """
    Raised when query embedding generation fails.

    Examples:
        - Embedding provider unavailable or timed out
        - Invalid or empty embedding returned by provider
        - Embedding vector dimension mismatch
        - Provider authentication failure

    The ``is_transient`` flag indicates whether the failure may resolve
    on retry (e.g., network timeout) or is permanent (e.g., auth failure).

    Attributes:
        is_transient: True if the failure is likely temporary (rate limit,
                      timeout). False for permanent failures (auth, bad config).
    """

    def __init__(
        self,
        message: str,
        *,
        is_transient: bool = False,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.is_transient = is_transient


class RetrievalQdrantError(RetrievalError):
    """
    Raised when the Qdrant search operation fails.

    Examples:
        - Qdrant service unavailable or connection refused
        - Connection timeout
        - Collection does not exist
        - Invalid vector dimension rejected by Qdrant
        - Authentication or configuration failure

    The ``is_transient`` flag distinguishes temporary infrastructure
    failures (connection reset, timeout) from permanent configuration
    failures (missing collection, dimension mismatch).

    Attributes:
        is_transient: True for connection/timeout failures eligible for
                      bounded retry. False for configuration/auth failures.
    """

    def __init__(
        self,
        message: str,
        *,
        is_transient: bool = False,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.is_transient = is_transient
