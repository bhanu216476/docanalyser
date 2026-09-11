"""
Embeddings package — production-ready embedding generation for the RAG pipeline.

Public API
----------
Service:
    EmbeddingService
    create_embedding_service

Providers:
    EmbeddingProvider
    FakeEmbeddingProvider
    OpenAIEmbeddingProvider

Models:
    EmbeddingRequest
    EmbeddingResult

Token Counting:
    TokenCounter
    CharApproxTokenCounter
    TiktokenCounter
    make_token_counter

Exceptions:
    EmbeddingError
    EmbeddingValidationError
    EmbeddingTokenLimitError
    EmbeddingProviderError
    EmbeddingRetryExhaustedError

Constants:
    DEFAULT_BATCH_SIZE
    DEFAULT_MAX_TOKENS
    DEFAULT_MAX_RETRIES
    DEFAULT_RETRY_BASE_DELAY
"""

from app.embeddings.exceptions import (
    EmbeddingError,
    EmbeddingProviderError,
    EmbeddingRetryExhaustedError,
    EmbeddingTokenLimitError,
    EmbeddingValidationError,
)
from app.embeddings.models import EmbeddedChunk, EmbeddingRequest, EmbeddingResult
from app.embeddings.providers import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.embeddings.service import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RETRY_BASE_DELAY,
    EmbeddingService,
    create_embedding_service,
)
from app.embeddings.token_counter import (
    CharApproxTokenCounter,
    TiktokenCounter,
    TokenCounter,
    make_token_counter,
)

__all__ = [
    # Service
    "EmbeddingService",
    "create_embedding_service",
    # Providers
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    # Models
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddedChunk",
    # Token Counting
    "TokenCounter",
    "CharApproxTokenCounter",
    "TiktokenCounter",
    "make_token_counter",
    # Exceptions
    "EmbeddingError",
    "EmbeddingValidationError",
    "EmbeddingTokenLimitError",
    "EmbeddingProviderError",
    "EmbeddingRetryExhaustedError",
    # Constants
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_BASE_DELAY",
]
