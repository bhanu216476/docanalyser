from __future__ import annotations

import pytest

from app.retrieval.hybrid_service import HybridRetrievalService
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.models import RetrievalFilter, RetrievalResult
from app.retrieval.reranker import IdentityReranker


def result(chunk_id: str) -> RetrievalResult:
    return RetrievalResult(chunk_id=chunk_id, content=f"content {chunk_id}", score=0.5)


class RecordingHybrid:
    candidate_top_k = 20

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, RetrievalFilter | None]] = []

    def retrieve(self, query: str, top_k: int | None = None, filters: RetrievalFilter | None = None) -> list[RetrievalResult]:
        self.calls.append((query, top_k or 0, filters))
        return [result("a"), result("b")]


class RecordingSource:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, RetrievalFilter | None]] = []

    def retrieve(self, query: str, top_k: int, filters: RetrievalFilter | None = None) -> list[RetrievalResult]:
        self.calls.append((query, top_k, filters))
        return self.results


class RecordingReranker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RetrievalResult], int]] = []

    def rerank(self, query: str, candidates: list[RetrievalResult], top_k: int) -> list[RetrievalResult]:
        self.calls.append((query, candidates, top_k))
        return candidates[:top_k]


def test_pipeline_passes_candidate_count_and_returns_final_count() -> None:
    hybrid = RecordingHybrid()
    reranker = RecordingReranker()
    service = HybridRetrievalService(
        hybrid,
        reranker,
        rerank_candidate_top_k=2,
        rerank_top_k=1,
    )
    retrieval_filter = RetrievalFilter(document_id="doc-1")

    results = service.retrieve("query", filters=retrieval_filter)

    assert hybrid.calls == [("query", 2, retrieval_filter)]
    assert reranker.calls[0][0] == "query"
    assert len(reranker.calls[0][1]) == 2
    assert reranker.calls[0][2] == 1
    assert len(results) == 1


def test_invalid_pipeline_limits_fail() -> None:
    hybrid = RecordingHybrid()
    reranker = RecordingReranker()
    with pytest.raises(ValueError):
        HybridRetrievalService(hybrid, reranker, rerank_candidate_top_k=21)
    with pytest.raises(ValueError):
        HybridRetrievalService(hybrid, reranker, rerank_candidate_top_k=2, rerank_top_k=3)

    service = HybridRetrievalService(
        hybrid, reranker, rerank_candidate_top_k=2, rerank_top_k=1
    )
    with pytest.raises(ValueError):
        service.retrieve("query", top_k=3)


def test_default_pipeline_demonstrates_20_20_to_20_to_5() -> None:
    dense = RecordingSource([result(f"dense-{index}") for index in range(20)])
    bm25 = RecordingSource([result(f"bm25-{index}") for index in range(20)])
    hybrid = HybridRetriever(dense, bm25)
    service = HybridRetrievalService(hybrid, IdentityReranker())

    results = service.retrieve("query")

    assert dense.calls[0][1] == 20
    assert bm25.calls[0][1] == 20
    assert len(hybrid.retrieve("query")) == 20
    assert len(results) == 5