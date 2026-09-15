"""
Reranked Pipeline — chains a Retriever with a Reranker.

Measures step-by-step latency with time.perf_counter() and returns
a RerankExperimentResult capturing full stage timing.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Optional

from app.retrieval.models import RetrievalFilter, RetrievalResult
from app.retrieval.retriever import Retriever
from app.reranking.base import Reranker
from app.reranking.metrics import compute_latency, compute_ranking_metrics
from app.reranking.models import (
    LatencyMetrics,
    RerankExperimentResult,
    RerankedResult,
)


class RerankedPipeline:
    """
    Full hybrid → reranker pipeline.

    Flow:
        Retriever.retrieve(query)  — timed separately
            ↓
        Reranker.rerank(query, candidates)  — timed separately
            ↓
        RerankExperimentResult

    Args:
        retriever:   Any Retriever protocol implementer (Dense, BM25, Hybrid…).
        reranker:    Any Reranker protocol implementer.
        top_k:       Final number of reranked results to return.
        candidate_k: Pool size for retrieval stage before reranking.
    """

    def __init__(
        self,
        retriever: Retriever,
        reranker: Reranker,
        top_k: int = 5,
        candidate_k: int = 20,
    ) -> None:
        if top_k <= 0:
            raise ValueError(f"top_k must be a positive integer, got {top_k}")
        if candidate_k < top_k:
            raise ValueError(
                f"candidate_k ({candidate_k}) must be >= top_k ({top_k})"
            )
        self.retriever = retriever
        self.reranker = reranker
        self.top_k = top_k
        self.candidate_k = candidate_k

    def run(
        self,
        query: str,
        filters: Optional[RetrievalFilter] = None,
        top_k: Optional[int] = None,
        candidate_k: Optional[int] = None,
    ) -> RerankExperimentResult:
        """
        Execute the full retrieval → reranking pipeline and return a
        detailed experiment result.

        Args:
            query:        User search query string.
            filters:      Optional metadata filter applied during retrieval.
            top_k:        Override final top-K (defaults to self.top_k).
            candidate_k:  Override candidate pool size (defaults to self.candidate_k).

        Returns:
            RerankExperimentResult with results, latencies, and ranking metrics.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        effective_top_k = top_k if top_k is not None else self.top_k
        effective_candidate_k = (
            candidate_k if candidate_k is not None else self.candidate_k
        )
        pipeline_start = time.perf_counter()

        # 1. Retrieval stage
        retrieval_start = time.perf_counter()
        candidates: list[RetrievalResult] = self.retriever.retrieve(
            query=query,
            top_k=effective_candidate_k,
            filters=filters,
        )
        retrieval_end = time.perf_counter()
        retrieval_latency_ms = (retrieval_end - retrieval_start) * 1000.0

        # 2. Reranking stage
        reranking_start = time.perf_counter()
        reranked: list[RerankedResult] = self.reranker.rerank(
            query=query,
            documents=candidates,
            top_k=effective_top_k,
        )
        reranking_end = time.perf_counter()
        reranking_latency_ms = (reranking_end - reranking_start) * 1000.0

        total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0

        latency = LatencyMetrics(
            retrieval_latency_ms=round(retrieval_latency_ms, 4),
            reranking_latency_ms=round(reranking_latency_ms, 4),
            total_latency_ms=round(total_latency_ms, 4),
        )

        ranking_metrics = compute_ranking_metrics(
            candidates=candidates,
            reranked=reranked,
            top_k=effective_top_k,
        )

        return RerankExperimentResult(
            query=query,
            candidate_count=len(candidates),
            initial_results=candidates,
            reranked_results=reranked,
            latency=latency,
            ranking_metrics=ranking_metrics,
        )
