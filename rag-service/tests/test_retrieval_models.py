"""
Unit tests for RetrievalRequest, RetrievalFilter, and RetrievalResult models.

Tests Pydantic validation rules without any external dependencies.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult


# ===========================================================================
# RetrievalFilter
# ===========================================================================


class TestRetrievalFilter:
    def test_empty_filter_is_empty(self) -> None:
        f = RetrievalFilter()
        assert f.is_empty is True

    def test_document_id_filter_not_empty(self) -> None:
        f = RetrievalFilter(document_id="doc-1")
        assert f.is_empty is False

    def test_file_type_filter_not_empty(self) -> None:
        f = RetrievalFilter(file_type="md")
        assert f.is_empty is False

    def test_source_filter_not_empty(self) -> None:
        f = RetrievalFilter(source="docs/handbook.md")
        assert f.is_empty is False

    def test_list_document_ids(self) -> None:
        f = RetrievalFilter(document_id=["doc-1", "doc-2"])
        assert f.document_id == ["doc-1", "doc-2"]
        assert f.is_empty is False

    def test_list_file_types(self) -> None:
        f = RetrievalFilter(file_type=["md", "txt"])
        assert f.file_type == ["md", "txt"]

    def test_chunk_index_filter(self) -> None:
        f = RetrievalFilter(chunk_index=3)
        assert f.chunk_index == 3
        assert f.is_empty is False

    def test_chunk_index_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RetrievalFilter(chunk_index=-1)
        assert "chunk_index" in str(exc_info.value)

    def test_section_filter(self) -> None:
        f = RetrievalFilter(section="Benefits")
        assert f.section == "Benefits"
        assert f.is_empty is False

    def test_filter_is_frozen(self) -> None:
        f = RetrievalFilter(document_id="doc-1")
        with pytest.raises(Exception):
            f.document_id = "doc-2"  # type: ignore[misc]

    def test_combined_filters_not_empty(self) -> None:
        f = RetrievalFilter(document_id="doc-1", file_type="md")
        assert f.is_empty is False


# ===========================================================================
# RetrievalRequest
# ===========================================================================


class TestRetrievalRequest:
    def test_valid_request_defaults(self) -> None:
        req = RetrievalRequest(query="How many leave days?")
        assert req.query == "How many leave days?"
        assert req.top_k == 10
        assert req.filters is None

    def test_query_is_stripped(self) -> None:
        req = RetrievalRequest(query="  How many leave days?  ")
        assert req.query == "How many leave days?"

    def test_empty_query_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RetrievalRequest(query="")
        assert "empty" in str(exc_info.value).lower() or "query" in str(exc_info.value).lower()

    def test_whitespace_only_query_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RetrievalRequest(query="   ")
        assert "empty" in str(exc_info.value).lower() or "query" in str(exc_info.value).lower()

    def test_custom_top_k(self) -> None:
        req = RetrievalRequest(query="test", top_k=5)
        assert req.top_k == 5

    def test_top_k_minimum_is_one(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalRequest(query="test", top_k=0)

    def test_top_k_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalRequest(query="test", top_k=-1)

    def test_top_k_above_maximum_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RetrievalRequest(query="test", top_k=9999)
        assert "maximum" in str(exc_info.value).lower() or "top_k" in str(exc_info.value).lower()

    def test_top_k_exactly_at_max(self) -> None:
        from app.core.config import settings
        req = RetrievalRequest(query="test", top_k=settings.retrieval_max_top_k)
        assert req.top_k == settings.retrieval_max_top_k

    def test_request_with_filter(self) -> None:
        req = RetrievalRequest(
            query="leave days",
            top_k=5,
            filters=RetrievalFilter(document_id="doc-1"),
        )
        assert req.filters is not None
        assert req.filters.document_id == "doc-1"

    def test_request_is_frozen(self) -> None:
        req = RetrievalRequest(query="test")
        with pytest.raises(Exception):
            req.query = "modified"  # type: ignore[misc]


# ===========================================================================
# RetrievalResult
# ===========================================================================


class TestRetrievalResult:
    def _make_result(self, **overrides) -> RetrievalResult:
        defaults = dict(
            chunk_id="doc-1:0",
            score=0.91,
            document_id="doc-1",
            chunk_index=0,
            content="Annual leave entitlement is 20 days.",
            file_name="hr_policy.md",
            file_type="md",
            source="docs/hr_policy.md",
        )
        defaults.update(overrides)
        return RetrievalResult(**defaults)

    def test_minimal_valid_result(self) -> None:
        result = self._make_result()
        assert result.chunk_id == "doc-1:0"
        assert result.score == pytest.approx(0.91)
        assert result.document_id == "doc-1"
        assert result.chunk_index == 0
        assert result.content == "Annual leave entitlement is 20 days."

    def test_optional_fields_default_none(self) -> None:
        result = self._make_result()
        assert result.section is None
        assert result.start_char is None
        assert result.end_char is None
        assert result.metadata == {}

    def test_optional_fields_populated(self) -> None:
        result = self._make_result(
            section="Benefits",
            start_char=100,
            end_char=200,
            metadata={"custom": "value"},
        )
        assert result.section == "Benefits"
        assert result.start_char == 100
        assert result.end_char == 200
        assert result.metadata == {"custom": "value"}

    def test_score_is_float(self) -> None:
        result = self._make_result(score=0.75)
        assert isinstance(result.score, float)

    def test_chunk_index_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            self._make_result(chunk_index=-1)

    def test_result_is_frozen(self) -> None:
        result = self._make_result()
        with pytest.raises(Exception):
            result.score = 0.5  # type: ignore[misc]

    def test_score_ranking_order_preserved(self) -> None:
        """Verify results maintain descending score ordering when constructed."""
        results = [
            self._make_result(score=0.91, chunk_id="doc-1:0"),
            self._make_result(score=0.87, chunk_id="doc-1:1"),
            self._make_result(score=0.83, chunk_id="doc-1:2"),
        ]
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
