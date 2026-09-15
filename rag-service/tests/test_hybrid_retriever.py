"""
Unit tests for HybridRetriever.

Uses deterministic mock retrievers to isolate HybridRetriever behaviour
from real Dense/BM25 dependencies and Qdrant.
"""

from __future__ import annotations

from typing import Optional

import pytest

from app.retrieval.exceptions import HybridRetrievalError, RetrievalQueryError
from app.retrieval.hybrid_retriever import HybridRetriever, create_hybrid_retriever
from app.retrieval.models import (
    HybridRetrievalRequest,
    HybridRetrievalResult,
    RetrievalFilter,
    RetrievalResult,
)
from app.retrieval.retriever import Retriever


# ---------------------------------------------------------------------------
# Mock Retrievers
# ---------------------------------------------------------------------------

class SuccessRetriever:
    """Statically configured mock retriever returning preset results."""

    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results
        self.last_query: Optional[str] = None
        self.last_top_k: Optional[int] = None
        self.last_filters: Optional[RetrievalFilter] = None

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_filters = filters
        return self._results[:top_k]


class FailRetriever:
    """Mock retriever that always raises an exception."""

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        raise RuntimeError("Simulated retrieval failure")


def _make_result(chunk_id: str, score: float, rank: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=f"Content of {chunk_id}",
        score=score,
        rank=rank,
        document_id="doc",
        file_name="test.md",
        file_type="md",
        source="/test.md",
    )


def _dense_results() -> list[RetrievalResult]:
    return [
        _make_result("A", 0.95, 1),
        _make_result("B", 0.85, 2),
        _make_result("C", 0.75, 3),
    ]


def _bm25_results() -> list[RetrievalResult]:
    return [
        _make_result("C", 8.42, 1),
        _make_result("A", 6.71, 2),
        _make_result("D", 5.98, 3),
    ]


# ---------------------------------------------------------------------------
# Core retrieval tests
# ---------------------------------------------------------------------------

class TestHybridRetrieverCore:
    def test_returns_hybrid_results(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            k=60,
        )
        results = retriever.retrieve("test query", top_k=4)
        assert len(results) > 0
        assert all(isinstance(r, HybridRetrievalResult) for r in results)

    def test_top_k_limits_output(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=SuccessRetriever(_bm25_results()),
        )
        results = retriever.retrieve("test", top_k=2)
        assert len(results) == 2

    def test_results_sorted_descending_by_rrf_score(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            k=60,
        )
        results = retriever.retrieve("test", top_k=4)
        scores = [r.rrf_score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_chunk_appearing_in_both_gets_both_ranks(self) -> None:
        """A chunk in both Dense and BM25 should have dense_rank and bm25_rank set."""
        # "A" is rank 1 dense and rank 2 bm25; "C" is rank 3 dense and rank 1 bm25
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            k=60,
        )
        results = retriever.retrieve("test", top_k=10)
        a = next((r for r in results if r.chunk_id == "A"), None)
        c = next((r for r in results if r.chunk_id == "C"), None)

        assert a is not None
        assert a.dense_rank is not None
        assert a.bm25_rank is not None

        assert c is not None
        assert c.dense_rank is not None
        assert c.bm25_rank is not None

    def test_chunk_only_in_dense_has_no_bm25_rank(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([_make_result("ONLY_DENSE", 0.9, 1)]),
            bm25_retriever=SuccessRetriever([_make_result("OTHER", 5.0, 1)]),
            k=60,
        )
        results = retriever.retrieve("query", top_k=10)
        only_dense = next(r for r in results if r.chunk_id == "ONLY_DENSE")
        assert only_dense.dense_rank is not None
        assert only_dense.bm25_rank is None

    def test_empty_returns_from_both_retrievers(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([]),
            bm25_retriever=SuccessRetriever([]),
            k=60,
        )
        results = retriever.retrieve("query", top_k=10)
        assert results == []

    def test_query_forwarded_to_both_retrievers(self) -> None:
        dense_mock = SuccessRetriever(_dense_results())
        bm25_mock = SuccessRetriever(_bm25_results())
        retriever = HybridRetriever(
            dense_retriever=dense_mock,
            bm25_retriever=bm25_mock,
            k=60,
        )
        retriever.retrieve("my search query", top_k=3)
        assert dense_mock.last_query == "my search query"
        assert bm25_mock.last_query == "my search query"


# ---------------------------------------------------------------------------
# Metadata filter propagation
# ---------------------------------------------------------------------------

class TestFilterPropagation:
    def test_filter_forwarded_to_both_retrievers(self) -> None:
        dense_mock = SuccessRetriever(_dense_results())
        bm25_mock = SuccessRetriever(_bm25_results())
        retriever = HybridRetriever(
            dense_retriever=dense_mock,
            bm25_retriever=bm25_mock,
        )
        filt = RetrievalFilter(file_type="md")
        retriever.retrieve("query", top_k=3, filters=filt)

        assert dense_mock.last_filters == filt
        assert bm25_mock.last_filters == filt

    def test_no_filter_forwarded_as_none(self) -> None:
        dense_mock = SuccessRetriever(_dense_results())
        bm25_mock = SuccessRetriever(_bm25_results())
        retriever = HybridRetriever(
            dense_retriever=dense_mock,
            bm25_retriever=bm25_mock,
        )
        retriever.retrieve("query", top_k=3, filters=None)
        assert dense_mock.last_filters is None
        assert bm25_mock.last_filters is None


# ---------------------------------------------------------------------------
# Error handling — allow_degraded=False (strict)
# ---------------------------------------------------------------------------

class TestErrorHandlingStrict:
    def test_dense_failure_raises_hybrid_error(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=FailRetriever(),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            allow_degraded=False,
        )
        with pytest.raises(HybridRetrievalError):
            retriever.retrieve("query", top_k=3)

    def test_bm25_failure_raises_hybrid_error(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=FailRetriever(),
            allow_degraded=False,
        )
        with pytest.raises(HybridRetrievalError):
            retriever.retrieve("query", top_k=3)


# ---------------------------------------------------------------------------
# Error handling — allow_degraded=True
# ---------------------------------------------------------------------------

class TestDegradedMode:
    def test_dense_failure_allows_bm25_fallback(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=FailRetriever(),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            allow_degraded=True,
        )
        results = retriever.retrieve("query", top_k=3)
        assert len(results) > 0

    def test_bm25_failure_allows_dense_fallback(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever(_dense_results()),
            bm25_retriever=FailRetriever(),
            allow_degraded=True,
        )
        results = retriever.retrieve("query", top_k=3)
        assert len(results) > 0

    def test_degraded_results_tagged_in_metadata(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=FailRetriever(),
            bm25_retriever=SuccessRetriever(_bm25_results()),
            allow_degraded=True,
        )
        results = retriever.retrieve("query", top_k=3)
        for r in results:
            assert r.metadata.get("degraded") is True
            assert "failed_sources" in r.metadata

    def test_both_fail_raises_hybrid_error_even_in_degraded(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=FailRetriever(),
            bm25_retriever=FailRetriever(),
            allow_degraded=True,
        )
        with pytest.raises(HybridRetrievalError):
            retriever.retrieve("query", top_k=3)


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------

class TestQueryValidation:
    def test_empty_query_raises(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([]),
            bm25_retriever=SuccessRetriever([]),
        )
        with pytest.raises(RetrievalQueryError):
            retriever.retrieve("", top_k=3)

    def test_whitespace_only_query_raises(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([]),
            bm25_retriever=SuccessRetriever([]),
        )
        with pytest.raises(RetrievalQueryError):
            retriever.retrieve("   ", top_k=3)

    def test_top_k_zero_raises(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([]),
            bm25_retriever=SuccessRetriever([]),
        )
        with pytest.raises(RetrievalQueryError):
            retriever.retrieve("query", top_k=0)

    def test_top_k_exceeds_max_raises(self) -> None:
        retriever = HybridRetriever(
            dense_retriever=SuccessRetriever([]),
            bm25_retriever=SuccessRetriever([]),
            max_top_k=5,
        )
        with pytest.raises(RetrievalQueryError):
            retriever.retrieve("query", top_k=6)


# ---------------------------------------------------------------------------
# HybridRetrievalRequest
# ---------------------------------------------------------------------------

class TestHybridRetrievalRequest:
    def test_retrieve_from_request_uses_k_override(self) -> None:
        dense_mock = SuccessRetriever(_dense_results())
        bm25_mock = SuccessRetriever(_bm25_results())
        retriever = HybridRetriever(
            dense_retriever=dense_mock,
            bm25_retriever=bm25_mock,
            k=60,
        )
        req = HybridRetrievalRequest(query="test", top_k=3, k=20)
        results = retriever.retrieve_from_request(req)
        assert len(results) <= 3

    def test_invalid_query_raises_validation_error(self) -> None:
        with pytest.raises(Exception):
            HybridRetrievalRequest(query="", top_k=5)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestCreateHybridRetriever:
    def test_factory_creates_instance(self) -> None:
        dense_mock = SuccessRetriever([])
        bm25_mock = SuccessRetriever([])
        retriever = create_hybrid_retriever(
            dense_retriever=dense_mock,
            bm25_retriever=bm25_mock,
        )
        assert isinstance(retriever, HybridRetriever)
