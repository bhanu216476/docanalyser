"""
Dense retrieval implementation using Qdrant vector similarity search.

Pipeline position:
    User Query
        ↓
    EmbeddingService.embed_texts([query])
        ↓
    Query Vector
        ↓
    QdrantClient.search()
        ↓
    ScoredPoint[]
        ↓
    RetrievalResult[]      ← this module

Responsibilities:
    ✓ Query validation (non-empty, top_k bounds)
    ✓ Query embedding via the existing EmbeddingService
    ✓ Embedding dimension validation before Qdrant call
    ✓ Metadata filter translation using existing FilterBuilder / VectorStoreFilter
    ✓ Qdrant similarity search with top_k and optional filter
    ✓ ScoredPoint → RetrievalResult mapping preserving Qdrant ranking order
    ✓ Empty result handling (returns [] — not an error)
    ✓ Clear, distinct exceptions for query / embedding / Qdrant failures
    ✓ Structured logging (no secrets, no full document content)
    ✓ Conforms to the Retriever protocol (structural)

Strictly Out of Scope:
    ✗ BM25 / sparse retrieval
    ✗ Hybrid fusion / RRF
    ✗ Reranking
    ✗ LLM / answer generation
    ✗ Post-retrieval Python-side filtering (filtering is pushed to Qdrant)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.core.config import settings
from app.embeddings.exceptions import (
    EmbeddingError,
    EmbeddingProviderError,
    EmbeddingRetryExhaustedError,
    EmbeddingValidationError,
)
from app.embeddings.service import EmbeddingService
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult
from app.vector_store.filters import FilterBuilder, VectorStoreFilter
from app.vector_store.qdrant_client import create_qdrant_client

logger = logging.getLogger(__name__)


class DenseRetriever:
    """
    Dense (vector) retrieval over a Qdrant collection.

    Executes a two-phase pipeline for each retrieval call:
        1. Embed the query text using the injected EmbeddingService.
        2. Execute a nearest-neighbour search in Qdrant using the query vector.

    The retriever uses the existing VectorStoreFilter / FilterBuilder
    abstraction to translate RetrievalFilter into native Qdrant filter
    objects, ensuring all filtering is pushed to the server.

    Args:
        embedding_service: Configured EmbeddingService used for query embedding.
        qdrant_client:     Configured QdrantClient for vector search.
        collection_name:   Qdrant collection to search. Defaults to settings value.
        vector_size:       Expected embedding dimension for validation. Defaults to settings value.
        max_top_k:         Hard upper bound on top_k. Defaults to settings.retrieval_max_top_k.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_client: Optional[QdrantClient] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        max_top_k: Optional[int] = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._client = qdrant_client if qdrant_client is not None else create_qdrant_client()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.vector_size = vector_size or settings.qdrant_vector_size
        self.max_top_k = max_top_k if max_top_k is not None else settings.retrieval_max_top_k

        logger.info(
            "DenseRetriever initialized: collection='%s', vector_size=%d, max_top_k=%d",
            self.collection_name,
            self.vector_size,
            self.max_top_k,
        )

    # -----------------------------------------------------------------------
    # Public API — conforms to Retriever protocol
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        """
        Execute a dense retrieval operation.

        Flow:
            query → EmbeddingService → query vector → Qdrant search → RetrievalResult[]

        Args:
            query:   User search query (stripped; must not be empty).
            top_k:   Number of top-K results. Must be 1 ≤ top_k ≤ max_top_k.
            filters: Optional metadata filters pushed to Qdrant.

        Returns:
            List of RetrievalResult ordered by descending similarity score,
            preserving Qdrant's native ranking order.
            Returns [] when no chunks match — not an error.

        Raises:
            RetrievalQueryError:     Invalid query text or top_k value.
            RetrievalEmbeddingError: Embedding generation failed.
            RetrievalQdrantError:    Qdrant search operation failed.
        """
        t_start = time.monotonic()

        # --- 1. Validate query and top_k ---
        query = self._validate_query(query)
        top_k = self._validate_top_k(top_k)

        logger.info(
            "Dense retrieval started: top_k=%d, has_filter=%s",
            top_k,
            filters is not None and not filters.is_empty if filters else False,
        )

        # --- 2. Generate query embedding ---
        query_vector = self._embed_query(query)

        # --- 3. Build Qdrant filter (push-down; no Python-side filtering) ---
        qdrant_filter = self._build_qdrant_filter(filters)

        # --- 4. Execute Qdrant similarity search ---
        scored_points = self._search_qdrant(
            query_vector=query_vector,
            top_k=top_k,
            qdrant_filter=qdrant_filter,
        )

        # --- 5. Map results ---
        results = [self._map_scored_point(sp) for sp in scored_points]

        elapsed_ms = (time.monotonic() - t_start) * 1000
        logger.info(
            "Dense retrieval completed: results=%d, top_k=%d, duration_ms=%.1f",
            len(results),
            top_k,
            elapsed_ms,
        )

        return results

    def retrieve_from_request(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Convenience method accepting a validated RetrievalRequest.

        Args:
            request: Fully validated RetrievalRequest instance.

        Returns:
            List of RetrievalResult in Qdrant ranking order.
        """
        return self.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _validate_query(self, query: str) -> str:
        """
        Strip and validate query string.

        Raises:
            RetrievalQueryError: If query is empty or whitespace-only after stripping.
        """
        if not isinstance(query, str):
            raise RetrievalQueryError(
                f"query must be a string, got {type(query).__name__}"
            )
        stripped = query.strip()
        if not stripped:
            raise RetrievalQueryError(
                "query cannot be empty or whitespace-only. "
                "Provide a meaningful search query."
            )
        return stripped

    def _validate_top_k(self, top_k: int) -> int:
        """
        Validate top_k range.

        Raises:
            RetrievalQueryError: If top_k is <= 0 or > max_top_k.
        """
        if not isinstance(top_k, int) or isinstance(top_k, bool):
            raise RetrievalQueryError(
                f"top_k must be an integer, got {type(top_k).__name__}"
            )
        if top_k <= 0:
            raise RetrievalQueryError(
                f"top_k must be greater than 0, got {top_k}"
            )
        if top_k > self.max_top_k:
            raise RetrievalQueryError(
                f"top_k={top_k} exceeds the maximum allowed value of {self.max_top_k}. "
                f"Reduce top_k to avoid unbounded vector searches."
            )
        return top_k

    def _embed_query(self, query: str) -> list[float]:
        """
        Generate a query embedding using the existing EmbeddingService.

        Reuses the same embedding model and configuration as stored document
        embeddings to ensure vector space compatibility.

        Raises:
            RetrievalEmbeddingError: On any embedding failure.
        """
        try:
            results = self._embedding_service.embed_texts([query])
        except EmbeddingValidationError as exc:
            raise RetrievalEmbeddingError(
                f"Query embedding validation failed: {exc}",
                is_transient=False,
            ) from exc
        except EmbeddingRetryExhaustedError as exc:
            raise RetrievalEmbeddingError(
                f"Query embedding failed after all retries: {exc}",
                is_transient=True,
            ) from exc
        except EmbeddingProviderError as exc:
            raise RetrievalEmbeddingError(
                f"Embedding provider error: {exc}",
                is_transient=exc.is_transient,
            ) from exc
        except EmbeddingError as exc:
            raise RetrievalEmbeddingError(
                f"Embedding service error: {exc}",
                is_transient=False,
            ) from exc
        except Exception as exc:
            raise RetrievalEmbeddingError(
                f"Unexpected error during query embedding: {exc}",
                is_transient=True,
            ) from exc

        if not results or not results[0].embedding:
            raise RetrievalEmbeddingError(
                "Embedding service returned an empty embedding for the query.",
                is_transient=False,
            )

        vector = results[0].embedding

        # Validate dimension matches the collection's vector size
        if len(vector) != self.vector_size:
            raise RetrievalEmbeddingError(
                f"Query embedding dimension {len(vector)} does not match "
                f"collection vector size {self.vector_size}. "
                f"Ensure the embedding model matches the collection configuration.",
                is_transient=False,
            )

        logger.debug("Query embedding generated: dimension=%d", len(vector))
        return vector

    def _build_qdrant_filter(
        self,
        filters: Optional[RetrievalFilter],
    ) -> Any:  # models.Filter | None
        """
        Convert a RetrievalFilter into a native Qdrant filter using FilterBuilder.

        Returns None when no filter conditions are set.
        Push-down is performed by Qdrant — no Python-side filtering.
        """
        if filters is None or filters.is_empty:
            return None

        vs_filter = VectorStoreFilter(
            document_id=filters.document_id,
            file_type=filters.file_type,
            source=filters.source,
            chunk_index=filters.chunk_index,
            file_name=filters.file_name,
            section=filters.section,
        )
        return FilterBuilder.build(vs_filter)

    def _search_qdrant(
        self,
        query_vector: list[float],
        top_k: int,
        qdrant_filter: Any,
    ) -> list[Any]:  # list[ScoredPoint]
        """
        Execute the Qdrant nearest-neighbour search using query_points().

        Uses the collection's configured distance metric (not overridden here).
        Returns an empty list if no points match — not treated as a failure.

        Note: qdrant-client >= 1.9 uses query_points() instead of search().
        The query vector is passed as ``query=list[float]`` and results are
        returned in ``response.points`` as a list of ScoredPoint objects.

        Raises:
            RetrievalQdrantError: On any Qdrant client error.
        """
        try:
            response = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )
            points = response.points
            logger.debug(
                "Qdrant query_points returned %d result(s) for collection '%s'",
                len(points),
                self.collection_name,
            )
            return points

        except UnexpectedResponse as exc:
            # HTTP-level errors from Qdrant REST API
            is_transient = exc.status_code >= 500 or exc.status_code in (408, 429)
            raise RetrievalQdrantError(
                f"Qdrant search failed with HTTP {exc.status_code}: {exc.content}",
                is_transient=is_transient,
            ) from exc

        except (ResponseHandlingException, ConnectionError, OSError) as exc:
            raise RetrievalQdrantError(
                f"Qdrant connection error during search: {exc}",
                is_transient=True,
            ) from exc

        except Exception as exc:
            err_str = str(exc).lower()
            is_transient = any(
                marker in err_str
                for marker in ("connection", "timeout", "unavailable", "reset", "refused")
            )
            raise RetrievalQdrantError(
                f"Unexpected error during Qdrant search: {exc}",
                is_transient=is_transient,
            ) from exc

    def _map_scored_point(self, scored_point: Any) -> RetrievalResult:
        """
        Map a Qdrant ScoredPoint to a typed RetrievalResult.

        Uses the VectorPayload fields stored in the point's payload.
        Preserves Qdrant's native score and ranking order.

        Args:
            scored_point: qdrant_client.models.ScoredPoint instance.

        Returns:
            RetrievalResult with all payload fields populated.
        """
        payload: dict[str, Any] = scored_point.payload or {}

        return RetrievalResult(
            chunk_id=payload.get("chunk_id", ""),
            score=float(scored_point.score),
            document_id=payload.get("document_id", ""),
            chunk_index=int(payload.get("chunk_index", 0)),
            content=payload.get("content", ""),
            file_name=payload.get("file_name", ""),
            file_type=payload.get("file_type", ""),
            source=payload.get("source", ""),
            section=payload.get("section"),
            start_char=payload.get("start_char"),
            end_char=payload.get("end_char"),
            metadata=payload.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def create_dense_retriever(
    embedding_service: Optional[EmbeddingService] = None,
    qdrant_client: Optional[QdrantClient] = None,
) -> DenseRetriever:
    """
    Convenience factory that creates a DenseRetriever from application settings.

    Args:
        embedding_service: Optional pre-built EmbeddingService.
                           If None, created via ``create_embedding_service()``.
        qdrant_client:     Optional pre-built QdrantClient.
                           If None, created via ``create_qdrant_client()``.

    Returns:
        Fully configured DenseRetriever instance.
    """
    from app.embeddings.service import create_embedding_service

    svc = embedding_service or create_embedding_service()
    client = qdrant_client or create_qdrant_client()

    return DenseRetriever(
        embedding_service=svc,
        qdrant_client=client,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.qdrant_vector_size,
        max_top_k=settings.retrieval_max_top_k,
    )
