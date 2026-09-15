"""
Hybrid Retriever implementation combining Dense and BM25 strategies with RRF.

Pipeline position:
    User Query (+ optional RetrievalFilter)
        │
        ├─────────────────────────────┬─────────────────────────────┐
        ▼                                                           ▼
    DenseRetriever.retrieve()                                   BM25Retriever.retrieve()
    (query, dense_top_k, filters)                               (query, bm25_top_k, filters)
        │                                                           │
        ▼                                                           ▼
    Dense Results (ranked)                                      BM25 Results (ranked)
        │                                                           │
        └─────────────────────────────┬─────────────────────────────┘
                                      ▼
                        Reciprocal Rank Fusion (RRF)
                                      │
                                      ▼
                        Deterministic Sort & Truncate
                                      │
                                      ▼
                          HybridRetrievalResult[]

Conforms to the Retriever protocol (app.retrieval.retriever.Retriever).
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Sequence

from app.core.config import settings
from app.retrieval.bm25_retriever import BM25Retriever, create_bm25_retriever
from app.retrieval.dense_retriever import DenseRetriever, create_dense_retriever
from app.retrieval.exceptions import (
    HybridRetrievalError,
    RetrievalQueryError,
)
from app.retrieval.models import (
    HybridRetrievalRequest,
    HybridRetrievalResult,
    RetrievalFilter,
    RetrievalResult,
)
from app.retrieval.retriever import Retriever
from app.retrieval.rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines dense semantic vector retrieval and BM25 lexical retrieval using
    Reciprocal Rank Fusion (RRF).

    Conforms structurally to the ``Retriever`` protocol.

    Args:
        dense_retriever: Configured Retriever for dense vector search.
        bm25_retriever:  Configured Retriever for lexical BM25 search.
        k:               RRF ranking constant (k > 0). Defaults to settings.rrf_k (60).
        dense_top_k:     Candidate pool size for dense retrieval before fusion.
        bm25_top_k:      Candidate pool size for BM25 retrieval before fusion.
        max_top_k:       Hard upper bound on top_k results.
        allow_degraded:  If False (default), raises HybridRetrievalError when any
                         retrieval source fails. If True, logs warning and fuses
                         results from surviving source(s).
    """

    def __init__(
        self,
        dense_retriever: Optional[Retriever] = None,
        bm25_retriever: Optional[Retriever] = None,
        k: Optional[int] = None,
        dense_top_k: Optional[int] = None,
        bm25_top_k: Optional[int] = None,
        max_top_k: Optional[int] = None,
        allow_degraded: bool = False,
    ) -> None:
        self.dense_retriever = dense_retriever or create_dense_retriever()
        self.bm25_retriever = bm25_retriever or create_bm25_retriever()
        self.k = k if k is not None else settings.rrf_k
        self.dense_top_k = (
            dense_top_k if dense_top_k is not None else settings.hybrid_dense_top_k
        )
        self.bm25_top_k = (
            bm25_top_k if bm25_top_k is not None else settings.hybrid_bm25_top_k
        )
        self.max_top_k = (
            max_top_k if max_top_k is not None else settings.hybrid_max_top_k
        )
        self.allow_degraded = allow_degraded

        if self.k <= 0:
            raise ValueError(f"RRF parameter k must be positive, got {self.k}")
        if self.max_top_k <= 0:
            raise ValueError(f"max_top_k must be positive, got {self.max_top_k}")
        if self.dense_top_k <= 0 or self.bm25_top_k <= 0:
            raise ValueError("Candidate pool sizes must be positive")

        logger.info(
            "HybridRetriever initialized: k=%d, dense_top_k=%d, bm25_top_k=%d, "
            "max_top_k=%d, allow_degraded=%s",
            self.k,
            self.dense_top_k,
            self.bm25_top_k,
            self.max_top_k,
            self.allow_degraded,
        )

    # -----------------------------------------------------------------------
    # Public API — conforms to Retriever protocol
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[HybridRetrievalResult]:
        """
        Execute hybrid retrieval combining dense and BM25 results with RRF.

        Flow:
            1. Validate query and top_k.
            2. Execute DenseRetriever with query, candidate pool size, and filters.
            3. Execute BM25Retriever with query, candidate pool size, and filters.
            4. Fuse dense and BM25 rankings via Reciprocal Rank Fusion.
            5. Truncate to requested top_k and return.

        Args:
            query:   Search query string (must be non-empty after stripping).
            top_k:   Maximum number of fused hybrid results to return.
            filters: Optional metadata filters applied before ranking in both retrievers.

        Returns:
            List of HybridRetrievalResult sorted descending by fused RRF score.

        Raises:
            RetrievalQueryError:  On invalid query or top_k.
            HybridRetrievalError: When a retriever fails (if not allow_degraded)
                                 or when all retrievers fail.
        """
        t_start = time.monotonic()

        validated_query = self._validate_query(query)
        validated_top_k = self._validate_top_k(top_k)

        dense_candidates: list[RetrievalResult] = []
        bm25_candidates: list[RetrievalResult] = []
        failed_sources: list[str] = []

        pool_dense_k = max(validated_top_k * 2, self.dense_top_k)
        pool_bm25_k = max(validated_top_k * 2, self.bm25_top_k)

        # 1. Fetch Dense Candidates
        try:
            dense_candidates = self.dense_retriever.retrieve(
                query=validated_query,
                top_k=pool_dense_k,
                filters=filters,
            )
        except Exception as exc:
            logger.error("Dense retrieval failed during hybrid search: %s", exc)
            if not self.allow_degraded:
                raise HybridRetrievalError(
                    f"Dense retrieval failed during hybrid search: {exc}",
                    details={"source": "dense", "error": str(exc)},
                ) from exc
            failed_sources.append("dense")

        # 2. Fetch BM25 Candidates
        try:
            bm25_candidates = self.bm25_retriever.retrieve(
                query=validated_query,
                top_k=pool_bm25_k,
                filters=filters,
            )
        except Exception as exc:
            logger.error("BM25 retrieval failed during hybrid search: %s", exc)
            if not self.allow_degraded:
                raise HybridRetrievalError(
                    f"BM25 retrieval failed during hybrid search: {exc}",
                    details={"source": "bm25", "error": str(exc)},
                ) from exc
            failed_sources.append("bm25")

        # 3. Check if all sources failed
        if failed_sources and len(failed_sources) >= 2:
            raise HybridRetrievalError(
                "All retrieval sources failed during hybrid search.",
                details={"failed_sources": failed_sources},
            )

        # 4. Reciprocal Rank Fusion
        rankings = {
            "dense": dense_candidates,
            "bm25": bm25_candidates,
        }
        # If a source failed in degraded mode, omit it from fusion
        for failed in failed_sources:
            rankings.pop(failed, None)

        hybrid_results = reciprocal_rank_fusion(
            rankings=rankings,
            k=self.k,
            top_k=validated_top_k,
        )

        # Tag results if operating in degraded mode
        if failed_sources:
            logger.warning(
                "Hybrid retrieval operating in degraded mode due to failed sources: %s",
                failed_sources,
            )
            tagged_results: list[HybridRetrievalResult] = []
            for item in hybrid_results:
                degraded_meta = dict(item.metadata)
                degraded_meta["degraded"] = True
                degraded_meta["failed_sources"] = failed_sources
                tagged_results.append(
                    HybridRetrievalResult(
                        chunk_id=item.chunk_id,
                        content=item.content,
                        score=item.score,
                        rrf_score=item.rrf_score,
                        rank=item.rank,
                        metadata=degraded_meta,
                        document_id=item.document_id,
                        chunk_index=item.chunk_index,
                        file_name=item.file_name,
                        file_type=item.file_type,
                        source=item.source,
                        section=item.section,
                        start_char=item.start_char,
                        end_char=item.end_char,
                        provenance=item.provenance,
                        dense_rank=item.dense_rank,
                        bm25_rank=item.bm25_rank,
                        source_ranks=item.source_ranks,
                    )
                )
            hybrid_results = tagged_results

        elapsed_ms = (time.monotonic() - t_start) * 1000
        logger.info(
            "Hybrid retrieval completed: %d results, top_k=%d, duration_ms=%.2f",
            len(hybrid_results),
            validated_top_k,
            elapsed_ms,
        )

        return hybrid_results

    def retrieve_from_request(
        self,
        request: HybridRetrievalRequest,
    ) -> list[HybridRetrievalResult]:
        """
        Execute hybrid retrieval from a validated HybridRetrievalRequest.
        """
        # Overrides from request if provided
        prev_k = self.k
        prev_degraded = self.allow_degraded
        prev_dense_k = self.dense_top_k
        prev_bm25_k = self.bm25_top_k

        try:
            if request.k is not None:
                self.k = request.k
            if request.allow_degraded:
                self.allow_degraded = request.allow_degraded
            if request.dense_top_k is not None:
                self.dense_top_k = request.dense_top_k
            if request.bm25_top_k is not None:
                self.bm25_top_k = request.bm25_top_k

            return self.retrieve(
                query=request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
        finally:
            self.k = prev_k
            self.allow_degraded = prev_degraded
            self.dense_top_k = prev_dense_k
            self.bm25_top_k = prev_bm25_k

    # -----------------------------------------------------------------------
    # Validation helpers
    # -----------------------------------------------------------------------

    def _validate_query(self, query: str) -> str:
        if not isinstance(query, str):
            raise RetrievalQueryError(
                f"Query must be a string, got {type(query).__name__}"
            )
        stripped = query.strip()
        if not stripped:
            raise RetrievalQueryError(
                "Query cannot be empty or whitespace-only."
            )
        return stripped

    def _validate_top_k(self, top_k: int) -> int:
        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise RetrievalQueryError(
                f"top_k must be an integer, got {type(top_k).__name__}"
            )
        if top_k <= 0:
            raise RetrievalQueryError(
                f"top_k must be a positive integer (got {top_k})."
            )
        if top_k > self.max_top_k:
            raise RetrievalQueryError(
                f"top_k={top_k} exceeds the maximum allowed value of {self.max_top_k}."
            )
        return top_k


def create_hybrid_retriever(
    dense_retriever: Optional[Retriever] = None,
    bm25_retriever: Optional[Retriever] = None,
    k: Optional[int] = None,
    dense_top_k: Optional[int] = None,
    bm25_top_k: Optional[int] = None,
    max_top_k: Optional[int] = None,
    allow_degraded: bool = False,
) -> HybridRetriever:
    """Factory function creating a configured HybridRetriever instance."""
    return HybridRetriever(
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        k=k,
        dense_top_k=dense_top_k,
        bm25_top_k=bm25_top_k,
        max_top_k=max_top_k,
        allow_degraded=allow_degraded,
    )
