"""
Retriever protocol — extensible retrieval strategy abstraction.

Defines a structural Protocol that all retrieval strategies must satisfy.
Using typing.Protocol (structural subtyping) means that DenseRetriever —
and any future BM25Retriever, HybridRetriever, etc. — automatically
conform without requiring explicit inheritance from a base class.

This abstraction decouples the rest of the application from Qdrant-specific
internals and allows the retrieval strategy to be swapped or composed
without touching API or orchestration layers.

Future strategies:
    - BM25Retriever     — keyword / sparse retrieval
    - HybridRetriever   — RRF fusion of dense + sparse
    - RerankedRetriever — wraps any Retriever with cross-encoder reranking
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from app.retrieval.models import RetrievalFilter, RetrievalResult


@runtime_checkable
class Retriever(Protocol):
    """
    Structural protocol for all retrieval strategies.

    Any object implementing ``retrieve()`` with this signature satisfies
    the protocol, enabling duck-typed composition without inheritance.

    Usage::

        def search(retriever: Retriever, query: str) -> list[RetrievalResult]:
            return retriever.retrieve(query=query, top_k=10)

    Current implementations:
        - DenseRetriever  (app.retrieval.dense_retriever)

    Planned implementations (future tasks):
        - BM25Retriever
        - HybridRetriever
    """

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        """
        Execute a retrieval operation and return ranked results.

        Args:
            query:   User search query string (must be non-empty after stripping).
            top_k:   Maximum number of results to return.
            filters: Optional metadata filters applied server-side.

        Returns:
            List of RetrievalResult ordered by descending relevance score.
            Returns an empty list when no chunks match — not an error.

        Raises:
            RetrievalQueryError:     On invalid query or top_k.
            RetrievalEmbeddingError: On embedding generation failure.
            RetrievalQdrantError:    On vector search failure.
        """
        ...  # pragma: no cover
