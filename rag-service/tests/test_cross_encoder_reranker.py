"""
Unit tests for CrossEncoderCandidateReranker.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from app.reranking.base import BaseReranker, Reranker
from app.reranking.cross_encoder import CrossEncoderCandidateReranker
from app.retrieval.models import RetrievalResult


def _make_candidate(
    chunk_id: str,
    score: float,
    rank: int,
    content: str = "Candidate content",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=content,
        score=score,
        rank=rank,
        document_id="doc-1",
        file_name="test.md",
        file_type="md",
        source="/test.md",
    )


class TestCrossEncoderCandidateReranker:
    def test_protocol_conformance(self) -> None:
        reranker = CrossEncoderCandidateReranker()
        assert isinstance(reranker, BaseReranker)
        assert isinstance(reranker, Reranker)

    def test_empty_candidates_returns_empty(self) -> None:
        reranker = CrossEncoderCandidateReranker()
        assert reranker.rerank("test query", []) == []

    def test_validation_errors(self) -> None:
        reranker = CrossEncoderCandidateReranker()
        with pytest.raises(ValueError, match="query must be a non-empty string"):
            reranker.rerank("   ", [_make_candidate("c1", 0.5, 1)])

        with pytest.raises(ValueError, match="top_k must be a positive integer"):
            reranker.rerank("test", [_make_candidate("c1", 0.5, 1)], top_k=0)

    def test_with_mock_model_scoring(self) -> None:
        mock_model = MagicMock()
        # Returns raw logits for 3 pairs
        mock_model.predict.return_value = [2.0, -1.0, 0.5]

        reranker = CrossEncoderCandidateReranker(model=mock_model)
        candidates = [
            _make_candidate("c1", 0.9, 1, "Content 1"),
            _make_candidate("c2", 0.8, 2, "Content 2"),
            _make_candidate("c3", 0.7, 3, "Content 3"),
        ]

        results = reranker.rerank("query", candidates, top_k=3)

        assert len(results) == 3
        # c1 had score 2.0 -> sigmoid ~0.8808, c3 had 0.5 -> sigmoid ~0.6225, c2 had -1.0 -> sigmoid ~0.2689
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c3"
        assert results[2].chunk_id == "c2"

        assert results[0].reranked_rank == 1
        assert results[1].reranked_rank == 2
        assert results[2].reranked_rank == 3

        # Retrieval ranks preserved
        assert results[0].retrieval_rank == 1
        assert results[1].retrieval_rank == 3
        assert results[2].retrieval_rank == 2

        # Scores normalized to [0, 1]
        for r in results:
            assert 0.0 <= r.reranker_score <= 1.0

    def test_nan_and_inf_sanitization(self) -> None:
        mock_model = MagicMock()
        mock_model.predict.return_value = [float("nan"), float("inf"), float("-inf")]

        reranker = CrossEncoderCandidateReranker(model=mock_model)
        candidates = [
            _make_candidate("c1", 0.9, 1),
            _make_candidate("c2", 0.8, 2),
            _make_candidate("c3", 0.7, 3),
        ]

        results = reranker.rerank("query", candidates, top_k=3)
        assert len(results) == 3
        for r in results:
            assert not math.isnan(r.reranker_score)
            assert not math.isinf(r.reranker_score)
            assert 0.0 <= r.reranker_score <= 1.0

    def test_fallback_on_model_exception(self) -> None:
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("GPU out of memory")

        reranker = CrossEncoderCandidateReranker(model=mock_model)
        candidates = [
            _make_candidate("c1", 0.9, 1),
            _make_candidate("c2", 0.5, 2),
        ]

        results = reranker.rerank("query", candidates, top_k=2)
        assert len(results) == 2
        # Graceful fallback: ordered by retrieval score
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c2"
        assert results[0].reranked_rank == 1
        assert results[1].reranked_rank == 2

    def test_top_k_clamping(self) -> None:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.2, 0.3, 0.4]

        reranker = CrossEncoderCandidateReranker(model=mock_model, default_top_k=2)
        candidates = [_make_candidate(f"c{i}", 0.5, i) for i in range(1, 5)]

        results = reranker.rerank("query", candidates, top_k=2)
        assert len(results) == 2
