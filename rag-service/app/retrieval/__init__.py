"""
Retrieval package — dense vector retrieval for the RAG pipeline.

Public API
----------
Retriever protocol:
    Retriever

Dense retrieval:
    DenseRetriever
    create_dense_retriever
    DenseRetrievalService
    cosine_similarity

Models:
    RetrievalFilter
    RetrievalRequest
    RetrievalProvenance
    RetrievalResult

Exceptions:
    RetrievalError
    RetrievalQueryError
    RetrievalEmbeddingError
    RetrievalQdrantError
"""

from __future__ import annotations

from app.retrieval.dense_retriever import (
    DenseRetriever,
    create_dense_retriever,
)
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import (
    RetrievalFilter,
    RetrievalProvenance,
    RetrievalRequest,
    RetrievalResult,
)
from app.retrieval.retriever import Retriever
from app.retrieval.service import DenseRetrievalService
from app.retrieval.similarity import cosine_similarity

__all__ = [
    # Protocol
    "Retriever",
    # Dense retrieval
    "DenseRetriever",
    "create_dense_retriever",
    "DenseRetrievalService",
    "cosine_similarity",
    # Models
    "RetrievalFilter",
    "RetrievalRequest",
    "RetrievalProvenance",
    "RetrievalResult",
    # Exceptions
    "RetrievalError",
    "RetrievalQueryError",
    "RetrievalEmbeddingError",
    "RetrievalQdrantError",
]