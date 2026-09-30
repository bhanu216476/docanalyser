"""
Retrieval package — dense vector and BM25 lexical retrieval
for the RAG pipeline.

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

Hybrid retrieval:
    HybridRetriever
    create_hybrid_retriever
    reciprocal_rank_fusion
    run_k_experiment
    KExperimentRecord
    format_k_comparison_table

Evaluation:
    BenchmarkComparison
    BenchmarkQuery
    RetrievalMetrics
    compare_dense_and_bm25
    format_comparison
    run_synthetic_benchmark

Models:
    RetrievalFilter
    RetrievalRequest
    RetrievalProvenance
    RetrievalResult
    HybridRetrievalRequest
    HybridRetrievalResult

Exceptions:
    RetrievalError
    RetrievalQueryError
    RetrievalEmbeddingError
    RetrievalQdrantError
    RetrievalIndexError
    HybridRetrievalError
"""

from __future__ import annotations

from app.retrieval.benchmark import (
    BenchmarkComparison,
    BenchmarkQuery,
    RetrievalMetrics,
    compare_dense_and_bm25,
    format_comparison,
    run_synthetic_benchmark,
)
from app.retrieval.bm25_index import BM25Index
from app.retrieval.bm25_retriever import (
    BM25Retriever,
    create_bm25_retriever,
)
from app.retrieval.cross_encoder_reranker import CrossEncoderReranker
from app.retrieval.dense_retriever import (
    DenseRetriever,
    create_dense_retriever,
)
from app.retrieval.exceptions import (
    HybridRetrievalError,
    RetrievalEmbeddingError,
    RetrievalError,
    RetrievalIndexError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.hybrid_retriever import (
    HybridRetriever,
    create_hybrid_retriever,
)
from app.retrieval.hybrid_service import HybridRetrievalService
from app.retrieval.models import (
    HybridRetrievalRequest,
    HybridRetrievalResult,
    RetrievalFilter,
    RetrievalProvenance,
    RetrievalRequest,
    RetrievalResult,
)
from app.retrieval.reranker import IdentityReranker, Reranker
from app.retrieval.retriever import Retriever
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.rrf_experiment import (
    KExperimentRecord,
    format_k_comparison_table,
    run_k_experiment,
)
from app.retrieval.service import DenseRetrievalService
from app.retrieval.similarity import cosine_similarity
from app.retrieval.tokenizer import BM25Tokenizer, tokenize

__all__ = [
    "BM25Index",
    # BM25 lexical retrieval
    "BM25Retriever",
    "BM25Tokenizer",
    # Evaluation
    "BenchmarkComparison",
    "BenchmarkQuery",
    "CrossEncoderReranker",
    "DenseRetrievalService",
    # Dense retrieval
    "DenseRetriever",
    "HybridRetrievalError",
    "HybridRetrievalRequest",
    "HybridRetrievalResult",
    "HybridRetrievalService",
    # Hybrid retrieval & RRF
    "HybridRetriever",
    "IdentityReranker",
    "KExperimentRecord",
    "Reranker",
    "RetrievalEmbeddingError",
    # Exceptions
    "RetrievalError",
    # Models
    "RetrievalFilter",
    "RetrievalIndexError",
    "RetrievalMetrics",
    "RetrievalProvenance",
    "RetrievalQdrantError",
    "RetrievalQueryError",
    "RetrievalRequest",
    "RetrievalResult",
    # Protocol
    "Retriever",
    "compare_dense_and_bm25",
    "cosine_similarity",
    "create_bm25_retriever",
    "create_dense_retriever",
    "create_hybrid_retriever",
    "format_comparison",
    "format_k_comparison_table",
    "reciprocal_rank_fusion",
    "run_k_experiment",
    "run_synthetic_benchmark",
    "tokenize",
]
