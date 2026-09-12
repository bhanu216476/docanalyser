"""
Unit tests for DenseRetriever.

All tests use:
    - Mock EmbeddingService (no real API calls)
    - Mock QdrantClient (no real Qdrant connection)

Coverage:
    - Query validation (empty, whitespace, non-string)
    - top_k validation (zero, negative, above max, default)
    - Embedding service called with correct query
    - Query vector sent to Qdrant correctly
    - ScoredPoint → RetrievalResult mapping (all fields)
    - Qdrant ranking order preserved
    - Empty result returns []
    - Metadata filters pushed to Qdrant (not applied in Python)
    - Embedding failure → RetrievalEmbeddingError
    - Qdrant connection failure → RetrievalQdrantError
    - Qdrant HTTP error → RetrievalQdrantError
    - Vector dimension mismatch → RetrievalEmbeddingError
    - retrieve_from_request() convenience method
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.embeddings.exceptions import (
    EmbeddingProviderError,
    EmbeddingRetryExhaustedError,
    EmbeddingValidationError,
)
from app.embeddings.models import EmbeddingResult
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult
from app.retrieval.retriever import Retriever

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DIM = 8
TEST_COLLECTION = "test_documents"
FAKE_VECTOR = [0.1] * TEST_DIM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_embedding_service(
    vector: list[float] = None,
    *,
    fail_with: Exception | None = None,
) -> MagicMock:
    """Return a mock EmbeddingService that returns the given vector or raises."""
    svc = MagicMock()
    if fail_with is not None:
        svc.embed_texts.side_effect = fail_with
    else:
        v = vector or FAKE_VECTOR
        svc.embed_texts.return_value = [
            EmbeddingResult(index=0, embedding=v, token_count=5)
        ]
    return svc


def make_scored_point(
    chunk_id: str = "doc-1:0",
    score: float = 0.91,
    document_id: str = "doc-1",
    chunk_index: int = 0,
    content: str = "Annual leave is 20 days.",
    file_name: str = "hr.md",
    file_type: str = "md",
    source: str = "docs/hr.md",
    section: str | None = "Benefits",
    start_char: int | None = 100,
    end_char: int | None = 200,
    metadata: dict | None = None,
) -> MagicMock:
    """Return a mock Qdrant ScoredPoint with the given fields in its payload."""
    sp = MagicMock()
    sp.score = score
    sp.payload = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "chunk_index": chunk_index,
        "content": content,
        "file_name": file_name,
        "file_type": file_type,
        "source": source,
        "section": section,
        "start_char": start_char,
        "end_char": end_char,
        "metadata": metadata or {},
    }
    return sp


def make_retriever(
    embedding_vector: list[float] = None,
    qdrant_results: list[Any] = None,
    embed_fail: Exception | None = None,
    qdrant_fail: Exception | None = None,
    vector_size: int = TEST_DIM,
    max_top_k: int = 100,
) -> tuple[DenseRetriever, MagicMock, MagicMock]:
    """
    Build a DenseRetriever with mocked EmbeddingService and QdrantClient.

    Returns (retriever, mock_embedding_service, mock_qdrant_client).
    """
    svc = make_embedding_service(vector=embedding_vector, fail_with=embed_fail)
    client = MagicMock()

    # query_points() returns a QueryResponse object whose .points is the list
    mock_response = MagicMock()
    mock_response.points = qdrant_results or []

    if qdrant_fail is not None:
        client.query_points.side_effect = qdrant_fail
    else:
        client.query_points.return_value = mock_response

    retriever = DenseRetriever(
        embedding_service=svc,
        qdrant_client=client,
        collection_name=TEST_COLLECTION,
        vector_size=vector_size,
        max_top_k=max_top_k,
    )
    return retriever, svc, client


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestRetrieverProtocol:
    def test_dense_retriever_conforms_to_protocol(self) -> None:
        retriever, _, _ = make_retriever()
        assert isinstance(retriever, Retriever)


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------


class TestQueryValidation:
    def test_valid_query_accepted(self) -> None:
        retriever, _, _ = make_retriever()
        results = retriever.retrieve("How many leave days?", top_k=5)
        assert results == []

    def test_empty_query_raises(self) -> None:
        retriever, _, _ = make_retriever()
        with pytest.raises(RetrievalQueryError, match="empty"):
            retriever.retrieve("")

    def test_whitespace_only_query_raises(self) -> None:
        retriever, _, _ = make_retriever()
        with pytest.raises(RetrievalQueryError, match="empty"):
            retriever.retrieve("   ")

    def test_query_is_stripped_before_embedding(self) -> None:
        retriever, svc, _ = make_retriever()
        retriever.retrieve("  casual leave  ", top_k=5)
        svc.embed_texts.assert_called_once_with(["casual leave"])

    def test_non_string_query_raises(self) -> None:
        retriever, _, _ = make_retriever()
        with pytest.raises(RetrievalQueryError):
            retriever.retrieve(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# top_k validation
# ---------------------------------------------------------------------------


class TestTopKValidation:
    def test_default_top_k_is_ten(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test")
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["limit"] == 10

    def test_custom_top_k_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test", top_k=7)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["limit"] == 7

    def test_zero_top_k_raises(self) -> None:
        retriever, _, _ = make_retriever()
        with pytest.raises(RetrievalQueryError, match="greater than 0"):
            retriever.retrieve("test", top_k=0)

    def test_negative_top_k_raises(self) -> None:
        retriever, _, _ = make_retriever()
        with pytest.raises(RetrievalQueryError, match="greater than 0"):
            retriever.retrieve("test", top_k=-5)

    def test_top_k_above_max_raises(self) -> None:
        retriever, _, _ = make_retriever(max_top_k=50)
        with pytest.raises(RetrievalQueryError, match="maximum"):
            retriever.retrieve("test", top_k=51)

    def test_top_k_at_max_allowed(self) -> None:
        retriever, _, client = make_retriever(max_top_k=50)
        retriever.retrieve("test", top_k=50)
        assert client.query_points.call_args[1]["limit"] == 50


# ---------------------------------------------------------------------------
# Embedding service interaction
# ---------------------------------------------------------------------------


class TestEmbeddingInteraction:
    def test_embedding_service_called_with_query(self) -> None:
        retriever, svc, _ = make_retriever()
        retriever.retrieve("How many casual leave days?", top_k=5)
        svc.embed_texts.assert_called_once_with(["How many casual leave days?"])

    def test_returned_vector_sent_to_qdrant(self) -> None:
        custom_vector = [0.5] * TEST_DIM
        retriever, _, client = make_retriever(embedding_vector=custom_vector)
        retriever.retrieve("test", top_k=5)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["query"] == custom_vector

    def test_collection_name_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test")
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["collection_name"] == TEST_COLLECTION

    def test_payload_requested_from_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test")
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("with_payload") is True

    def test_vectors_not_requested_from_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test")
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("with_vectors") is False


# ---------------------------------------------------------------------------
# Dense retrieval end-to-end mapping
# ---------------------------------------------------------------------------


class TestRetrievalMapping:
    def test_single_result_mapped_correctly(self) -> None:
        sp = make_scored_point(
            chunk_id="doc-1:0",
            score=0.91,
            document_id="doc-1",
            chunk_index=0,
            content="Annual leave is 20 days.",
            file_name="hr.md",
            file_type="md",
            source="docs/hr.md",
            section="Benefits",
            start_char=100,
            end_char=200,
            metadata={"custom": "value"},
        )
        retriever, _, _ = make_retriever(qdrant_results=[sp])
        results = retriever.retrieve("leave days")

        assert len(results) == 1
        r = results[0]
        assert r.chunk_id == "doc-1:0"
        assert r.score == pytest.approx(0.91)
        assert r.document_id == "doc-1"
        assert r.chunk_index == 0
        assert r.content == "Annual leave is 20 days."
        assert r.file_name == "hr.md"
        assert r.file_type == "md"
        assert r.source == "docs/hr.md"
        assert r.section == "Benefits"
        assert r.start_char == 100
        assert r.end_char == 200
        assert r.metadata == {"custom": "value"}

    def test_multiple_results_preserve_qdrant_order(self) -> None:
        """Verify Qdrant ranking order is preserved, not re-sorted."""
        sps = [
            make_scored_point(score=0.91, chunk_id="doc-1:0"),
            make_scored_point(score=0.87, chunk_id="doc-1:1"),
            make_scored_point(score=0.83, chunk_id="doc-1:2"),
        ]
        retriever, _, _ = make_retriever(qdrant_results=sps)
        results = retriever.retrieve("test", top_k=3)

        assert len(results) == 3
        assert results[0].score == pytest.approx(0.91)
        assert results[1].score == pytest.approx(0.87)
        assert results[2].score == pytest.approx(0.83)
        assert results[0].chunk_id == "doc-1:0"
        assert results[1].chunk_id == "doc-1:1"
        assert results[2].chunk_id == "doc-1:2"

    def test_result_is_retrieval_result_type(self) -> None:
        sp = make_scored_point()
        retriever, _, _ = make_retriever(qdrant_results=[sp])
        results = retriever.retrieve("test")
        assert all(isinstance(r, RetrievalResult) for r in results)


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    def test_empty_qdrant_response_returns_empty_list(self) -> None:
        retriever, _, _ = make_retriever(qdrant_results=[])
        results = retriever.retrieve("How many leave days?", top_k=10)
        assert results == []

    def test_empty_result_is_not_an_exception(self) -> None:
        retriever, _, _ = make_retriever(qdrant_results=[])
        # Should not raise
        results = retriever.retrieve("obscure query with no match")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Metadata filters
# ---------------------------------------------------------------------------


class TestMetadataFilters:
    def test_no_filter_passes_none_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test")
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is None

    def test_empty_filter_passes_none_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        retriever.retrieve("test", filters=RetrievalFilter())
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is None

    def test_document_id_filter_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        f = RetrievalFilter(document_id="doc-42")
        retriever.retrieve("test", filters=f)
        call_kwargs = client.query_points.call_args[1]
        # Verify a non-None filter was passed to Qdrant
        assert call_kwargs.get("query_filter") is not None

    def test_file_type_filter_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        f = RetrievalFilter(file_type="md")
        retriever.retrieve("test", filters=f)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is not None

    def test_source_filter_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        f = RetrievalFilter(source="docs/handbook.md")
        retriever.retrieve("test", filters=f)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is not None

    def test_combined_filters_passed_to_qdrant(self) -> None:
        retriever, _, client = make_retriever()
        f = RetrievalFilter(document_id="doc-1", file_type="md", source="docs/hr.md")
        retriever.retrieve("test", filters=f)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is not None

    def test_filter_is_not_applied_in_python(self) -> None:
        """All filtering must happen server-side; Python should not re-filter."""
        # Return two scored points with different document IDs
        sp1 = make_scored_point(chunk_id="doc-1:0", document_id="doc-1")
        sp2 = make_scored_point(chunk_id="doc-2:0", document_id="doc-2")
        retriever, _, client = make_retriever(qdrant_results=[sp1, sp2])
        # Apply filter for doc-1 only; Qdrant mock still returns both (simulating
        # no real filter applied by the mock). Python must NOT further filter.
        f = RetrievalFilter(document_id="doc-1")
        results = retriever.retrieve("test", filters=f)
        # DenseRetriever should return whatever Qdrant returned, unchanged
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Embedding failure error handling
# ---------------------------------------------------------------------------


class TestEmbeddingFailures:
    def test_embedding_validation_error_raises_retrieval_embedding_error(self) -> None:
        retriever, _, _ = make_retriever(
            embed_fail=EmbeddingValidationError("empty text")
        )
        with pytest.raises(RetrievalEmbeddingError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is False

    def test_embedding_provider_transient_error(self) -> None:
        retriever, _, _ = make_retriever(
            embed_fail=EmbeddingProviderError("rate limit", is_transient=True)
        )
        with pytest.raises(RetrievalEmbeddingError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_embedding_provider_permanent_error(self) -> None:
        retriever, _, _ = make_retriever(
            embed_fail=EmbeddingProviderError("auth failure", is_transient=False)
        )
        with pytest.raises(RetrievalEmbeddingError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is False

    def test_embedding_retry_exhausted_error(self) -> None:
        retriever, _, _ = make_retriever(
            embed_fail=EmbeddingRetryExhaustedError(
                attempts=3, batch_index=0, cause=RuntimeError("timeout")
            )
        )
        with pytest.raises(RetrievalEmbeddingError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_vector_dimension_mismatch_raises(self) -> None:
        # Return a vector of wrong dimension
        wrong_dim_vector = [0.1] * (TEST_DIM + 4)
        retriever, _, _ = make_retriever(embedding_vector=wrong_dim_vector)
        with pytest.raises(RetrievalEmbeddingError) as exc_info:
            retriever.retrieve("test")
        assert "dimension" in str(exc_info.value).lower()
        assert exc_info.value.is_transient is False


# ---------------------------------------------------------------------------
# Qdrant failure error handling
# ---------------------------------------------------------------------------


class TestQdrantFailures:
    def test_qdrant_connection_error_raises_retrieval_qdrant_error(self) -> None:
        retriever, _, _ = make_retriever(
            qdrant_fail=ConnectionError("connection refused")
        )
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_qdrant_os_error_raises_retrieval_qdrant_error(self) -> None:
        retriever, _, _ = make_retriever(qdrant_fail=OSError("socket error"))
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_qdrant_response_handling_exception(self) -> None:
        retriever, _, _ = make_retriever(
            qdrant_fail=ResponseHandlingException(Exception("handler error"))
        )
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_qdrant_unexpected_response_5xx(self) -> None:
        exc = UnexpectedResponse(
            status_code=503,
            reason_phrase="Service Unavailable",
            content=b"Service Unavailable",
            headers={},
        )
        retriever, _, _ = make_retriever(qdrant_fail=exc)
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True

    def test_qdrant_unexpected_response_4xx(self) -> None:
        exc = UnexpectedResponse(
            status_code=400,
            reason_phrase="Bad Request",
            content=b"Bad Request",
            headers={},
        )
        retriever, _, _ = make_retriever(qdrant_fail=exc)
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is False

    def test_qdrant_timeout_error(self) -> None:
        retriever, _, _ = make_retriever(
            qdrant_fail=Exception("connection timeout")
        )
        with pytest.raises(RetrievalQdrantError) as exc_info:
            retriever.retrieve("test")
        assert exc_info.value.is_transient is True


# ---------------------------------------------------------------------------
# retrieve_from_request convenience method
# ---------------------------------------------------------------------------


class TestRetrieveFromRequest:
    def test_retrieve_from_request_calls_retrieve_correctly(self) -> None:
        sp = make_scored_point(score=0.88)
        retriever, svc, client = make_retriever(qdrant_results=[sp])

        request = RetrievalRequest(
            query="How many casual leave days?",
            top_k=5,
            filters=RetrievalFilter(document_id="doc-1"),
        )
        results = retriever.retrieve_from_request(request)

        assert len(results) == 1
        svc.embed_texts.assert_called_once_with(["How many casual leave days?"])
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["limit"] == 5
        assert call_kwargs["query_filter"] is not None  # filter passed through

    def test_retrieve_from_request_no_filter(self) -> None:
        retriever, _, client = make_retriever()
        request = RetrievalRequest(query="test query", top_k=3)
        retriever.retrieve_from_request(request)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs.get("query_filter") is None
