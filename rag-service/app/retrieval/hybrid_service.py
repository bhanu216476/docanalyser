"""Orchestration for hybrid retrieval followed by candidate reranking."""

from __future__ import annotations

from app.core.config import settings
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult
from app.retrieval.reranker import Reranker


class HybridRetrievalService:
    """Run hybrid candidate retrieval and then query-aware reranking."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        reranker: Reranker,
        rerank_candidate_top_k: int | None = None,
        rerank_top_k: int | None = None,
    ) -> None:
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker
        self.rerank_candidate_top_k = (
            rerank_candidate_top_k
            if rerank_candidate_top_k is not None
            else settings.rerank_candidate_top_k
        )
        self.rerank_top_k = (
            rerank_top_k if rerank_top_k is not None else settings.rerank_top_k
        )
        self._validate_configuration()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve hybrid candidates and return their reranked top results."""
        output_top_k = self.rerank_top_k if top_k is None else top_k
        _validate_positive_int(output_top_k, "top_k")
        if output_top_k > self.rerank_candidate_top_k:
            raise ValueError(
                "top_k must be less than or equal to rerank_candidate_top_k"
            )

        candidates = self.hybrid_retriever.retrieve(
            query=query,
            top_k=self.rerank_candidate_top_k,
            filters=filters,
        )
        return self.reranker.rerank(query, candidates, top_k=output_top_k)

    def retrieve_from_request(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Run the pipeline using a validated retrieval request."""
        return self.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )

    def _validate_configuration(self) -> None:
        _validate_positive_int(self.rerank_candidate_top_k, "rerank_candidate_top_k")
        _validate_positive_int(self.rerank_top_k, "rerank_top_k")
        if self.rerank_top_k > self.rerank_candidate_top_k:
            raise ValueError(
                "rerank_top_k must be less than or equal to rerank_candidate_top_k"
            )
        hybrid_limit = getattr(self.hybrid_retriever, "candidate_top_k", None)
        if hybrid_limit is not None and self.rerank_candidate_top_k > hybrid_limit:
            raise ValueError(
                "rerank_candidate_top_k must be less than or equal to "
                "hybrid candidate_top_k"
            )


def _validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")