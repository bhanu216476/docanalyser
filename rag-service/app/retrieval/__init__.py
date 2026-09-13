"""
Retrieval package — dense vector and BM25 lexical retrieval for the RAG pipeline.

Public API
----------
Retriever protocol:
    Retriever

Dense retrieval:
    DenseRetriever
    create_dense_retriever
    DenseRetrievalService
    cosine_similarity

BM25 lexical retrieval:
    BM25Retriever
    create_bm25_retriever
    BM25Index
    BM25Tokenizer
    tokenize

Models:
    RetrievalFilter
    RetrievalRequest
    RetrievalResult

Exceptions:
    RetrievalError
    RetrievalQueryError
    RetrievalEmbeddingError
    RetrievalQdrantError
    RetrievalIndexError
"""

from __future__ import annotations

from app.retrieval.bm25_index import BM25Index
from app.retrieval.bm25_retriever import (
    BM25Retriever,
    create_bm25_retriever,
)
from app.retrieval.dense_retriever import (
    DenseRetriever,
    create_dense_retriever,
)
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalError,
    RetrievalIndexError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import (
    RetrievalFilter,
    RetrievalRequest,
    RetrievalResult,
)
from app.retrieval.retriever import Retriever
from app.retrieval.service import DenseRetrievalService
from app.retrieval.similarity import cosine_similarity
from app.retrieval.tokenizer import BM25Tokenizer, tokenize

__all__ = [
    # Protocol
    "Retriever",
    # Dense retrieval
    "DenseRetriever",
    "create_dense_retriever",
    "DenseRetrievalService",
    "cosine_similarity",
    # BM25 lexical retrieval
    "BM25Retriever",
    "create_bm25_retriever",
    "BM25Index",
    "BM25Tokenizer",
    "tokenize",
    # Models
    "RetrievalFilter",
    "RetrievalRequest",
    "RetrievalResult",
    # Exceptions
    "RetrievalError",
    "RetrievalQueryError",
    "RetrievalEmbeddingError",
    "RetrievalQdrantError",
    "RetrievalIndexError",
]
