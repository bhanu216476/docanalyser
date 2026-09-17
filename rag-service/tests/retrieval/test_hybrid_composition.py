from __future__ import annotations

import pytest

from app.retrieval.exceptions import RetrievalQueryError
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult


def result(chunk_id: str, score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(chunk_id=chunk_id, content=f"content {chunk_id}", score=score)


class RecordingRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, RetrievalFilter | None]] = []

    def retrieve(self, query: str, top_k: int, filters: RetrievalFilter | None = None) -> list[RetrievalResult]:
        self.calls.append((query, top_k, filters))
        return self.results


def test_calls_dense_and_bm25_with_configured_values_and_filter() -> None:
    dense = RecordingRetriever([result("dense")])
    bm25 = RecordingRetriever([result("lexical")])
    retrieval_filter = RetrievalFilter(document_id="doc-1")
    hybrid = HybridRetriever(
        dense,
        bm25,
        dense_top_k=20,
        bm25_top_k=20,
        candidate_top_k=2,
        rrf_k=60,
    )

    fused = hybrid.retrieve("query", filters=retrieval_filter)

    assert dense.calls == [("query", 20, retrieval_filter)]
    assert bm25.calls == [("query", 20, retrieval_filter)]
    assert [item.chunk_id for item in fused] == ["dense", "lexical"]


def test_candidate_limit_and_request_are_supported() -> None:
    dense = RecordingRetriever([result("a"), result("b")])
    bm25 = RecordingRetriever([result("c"), result("d")])
    hybrid = HybridRetriever(dense, bm25, candidate_top_k=3)

    fused = hybrid.retrieve_from_request(RetrievalRequest(query="query", top_k=2))

    assert len(fused) == 2
    assert dense.calls[0][1] == 20
    assert bm25.calls[0][1] == 20


@pytest.mark.parametrize(
    "dense_results,bm25_results,expected",
    [([], [result("bm25")], ["bm25"]), ([result("dense")], [], ["dense"]), ([], [], [])],
)
def test_empty_source_results_are_handled(
    dense_results: list[RetrievalResult],
    bm25_results: list[RetrievalResult],
    expected: list[str],
) -> None:
    hybrid = HybridRetriever(
        RecordingRetriever(dense_results),
        RecordingRetriever(bm25_results),
        candidate_top_k=2,
    )

    assert [item.chunk_id for item in hybrid.retrieve("query")] == expected


def test_invalid_runtime_top_k_and_configuration_fail_clearly() -> None:
    dense = RecordingRetriever([])
    bm25 = RecordingRetriever([])
    with pytest.raises(ValueError):
        HybridRetriever(dense, bm25, candidate_top_k=0)
    with pytest.raises(ValueError):
        HybridRetriever(dense, bm25, dense_top_k=1, bm25_top_k=1, candidate_top_k=3)

    hybrid = HybridRetriever(dense, bm25, candidate_top_k=2)
    with pytest.raises(RetrievalQueryError):
        hybrid.retrieve("query", top_k=3)