"""
API tests for POST /api/retrieval/hybrid.

Uses TestClient with mocked HybridRetriever to test endpoint behavior
without external infrastructure.
"""

from __future__ import annotations

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.api.retrieval import set_hybrid_retriever
from app.main import app
from app.retrieval.exceptions import HybridRetrievalError, RetrievalQueryError
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.models import (
    HybridRetrievalRequest,
    HybridRetrievalResult,
    RetrievalFilter,
)


# ---------------------------------------------------------------------------
# Mock HybridRetriever
# ---------------------------------------------------------------------------

class MockHybridRetriever:
    """Configurable mock HybridRetriever for API tests."""

    def __init__(
        self,
        results: list[HybridRetrievalResult] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._raise_exc = raise_exc

    def retrieve(self, query: str, top_k: int = 10, filters=None) -> list[HybridRetrievalResult]:
        if self._raise_exc:
            raise self._raise_exc
        return self._results[:top_k]

    def retrieve_from_request(self, request: HybridRetrievalRequest) -> list[HybridRetrievalResult]:
        if self._raise_exc:
            raise self._raise_exc
        return self._results[: request.top_k]


def _make_hybrid_result(chunk_id: str, rrf_score: float, rank: int) -> HybridRetrievalResult:
    return HybridRetrievalResult(
        chunk_id=chunk_id,
        content=f"Content of {chunk_id}",
        score=rrf_score,
        rrf_score=rrf_score,
        rank=rank,
        document_id="doc",
        file_name="test.md",
        file_type="md",
        source="/test.md",
        dense_rank=rank,
        bm25_rank=rank,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Successful retrieval
# ---------------------------------------------------------------------------

class TestHybridEndpointSuccess:
    def test_returns_200_with_results(self, client: TestClient) -> None:
        mock_results = [
            _make_hybrid_result("chunk-A", 0.035, 1),
            _make_hybrid_result("chunk-B", 0.028, 2),
        ]
        set_hybrid_retriever(MockHybridRetriever(results=mock_results))

        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test query", "top_k": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["chunk_id"] == "chunk-A"
        assert data[0]["rrf_score"] == pytest.approx(0.035)

    def test_returns_empty_list_when_no_results(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(results=[]))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "obscure query", "top_k": 5},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_top_k_limits_results(self, client: TestClient) -> None:
        mock_results = [
            _make_hybrid_result(f"chunk-{i}", 0.1 - i * 0.01, i + 1)
            for i in range(5)
        ]
        set_hybrid_retriever(MockHybridRetriever(results=mock_results))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test", "top_k": 3},
        )
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_response_includes_rrf_score_and_source_ranks(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(results=[
            _make_hybrid_result("chunk-A", 0.033, 1)
        ]))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test", "top_k": 1},
        )
        assert response.status_code == 200
        item = response.json()[0]
        assert "rrf_score" in item
        assert "dense_rank" in item
        assert "bm25_rank" in item


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestHybridEndpointValidation:
    def test_empty_query_returns_422(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever())
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "", "top_k": 5},
        )
        assert response.status_code == 422

    def test_missing_query_returns_422(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever())
        response = client.post(
            "/api/retrieval/hybrid",
            json={"top_k": 5},
        )
        assert response.status_code == 422

    def test_top_k_zero_returns_422(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever())
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test", "top_k": 0},
        )
        assert response.status_code == 422

    def test_retrieval_query_error_returns_422(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(
            raise_exc=RetrievalQueryError("invalid query")
        ))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "valid query", "top_k": 5},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Service errors
# ---------------------------------------------------------------------------

class TestHybridEndpointErrors:
    def test_hybrid_retrieval_error_returns_503(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(
            raise_exc=HybridRetrievalError("retriever failure")
        ))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test query", "top_k": 5},
        )
        assert response.status_code == 503

    def test_unexpected_error_returns_500(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(
            raise_exc=RuntimeError("unexpected failure")
        ))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test query", "top_k": 5},
        )
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Optional fields (k, filters)
# ---------------------------------------------------------------------------

class TestHybridEndpointOptions:
    def test_with_k_parameter(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(results=[]))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test", "top_k": 5, "k": 40},
        )
        assert response.status_code == 200

    def test_with_allow_degraded(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(results=[]))
        response = client.post(
            "/api/retrieval/hybrid",
            json={"query": "test", "top_k": 5, "allow_degraded": True},
        )
        assert response.status_code == 200

    def test_with_metadata_filter(self, client: TestClient) -> None:
        set_hybrid_retriever(MockHybridRetriever(results=[]))
        response = client.post(
            "/api/retrieval/hybrid",
            json={
                "query": "test",
                "top_k": 5,
                "filters": {"file_type": "md"},
            },
        )
        assert response.status_code == 200
