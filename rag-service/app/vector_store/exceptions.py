"""
Vector store exceptions hierarchy.

Defines clear, domain-specific exceptions for Qdrant vector storage operations.
Ensures low-level client errors are not leaked across layer boundaries and that
transient failures can be distinguished from permanent configuration/validation bugs.
"""

from __future__ import annotations


class VectorStoreError(Exception):
    """Base exception for all vector store errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VectorStoreConnectionError(VectorStoreError):
    """
    Raised when connection to Qdrant fails or times out.

    Typically transient and eligible for bounded retry.
    """

    def __init__(self, message: str, is_transient: bool = True, details: dict | None = None) -> None:
        super().__init__(message, details=details)
        self.is_transient = is_transient


class CollectionConfigError(VectorStoreError):
    """
    Raised when an existing collection's configuration does not match application settings.

    For example, vector size mismatch or incompatible distance metric.
    Non-transient; requires manual migration or recreation.
    """


class VectorValidationError(VectorStoreError):
    """
    Raised when vector geometry, types, or chunk/embedding counts are invalid.

    Non-transient; caller must fix inputs before retrying.
    """


class FilterValidationError(VectorStoreError):
    """
    Raised when an invalid, illegal, or un-indexed field is used in a filter.

    Non-transient.
    """


class VectorStoreBatchError(VectorStoreError):
    """
    Raised when a batch upsert operation encounters a permanent or unrecoverable error.
    """
