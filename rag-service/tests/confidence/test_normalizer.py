"""
Unit tests for ScoreNormalizer across Dense, BM25, RRF, and Reranker scores.
"""

import math
import pytest

from app.confidence.normalizer import ScoreNormalizer
from app.retrieval.models import HybridRetrievalResult, RetrievalResult
from app.reranking.models import RerankedResult


class TestScoreNormalizer:
    def test_clamp(self) -> None:
        assert ScoreNormalizer.clamp(0.5) == 0.5
        assert ScoreNormalizer.clamp(-0.2) == 0.0
        assert ScoreNormalizer.clamp(1.5) == 1.0
        assert ScoreNormalizer.clamp(float("nan")) == 0.0
        assert ScoreNormalizer.clamp(float("inf")) == 0.0

    def test_normalize_cosine(self) -> None:
        # Standard clamping
        assert ScoreNormalizer.normalize_cosine(0.85) == 0.85
        assert ScoreNormalizer.normalize_cosine(1.2) == 1.0
        assert ScoreNormalizer.normalize_cosine(-0.1) == 0.0

        # With negative mapping
        assert ScoreNormalizer.normalize_cosine(-1.0, allow_negative=True) == 0.0
        assert ScoreNormalizer.normalize_cosine(0.0, allow_negative=True) == 0.5
        assert ScoreNormalizer.normalize_cosine(1.0, allow_negative=True) == 1.0

        # Non-finite
        assert ScoreNormalizer.normalize_cosine(float("nan")) == 0.0
        assert ScoreNormalizer.normalize_cosine(float("-inf")) == 0.0

    def test_normalize_bm25(self) -> None:
        # Zero or negative
        assert ScoreNormalizer.normalize_bm25(0.0) == 0.0
        assert ScoreNormalizer.normalize_bm25(-5.0) == 0.0

        # Soft saturation: at score == k_norm (10.0), normalized is 0.5
        assert ScoreNormalizer.normalize_bm25(10.0, k_norm=10.0) == 0.5

        # Very high score approaches 1.0
        high = ScoreNormalizer.normalize_bm25(1000.0, k_norm=10.0)
        assert 0.99 <= high <= 1.0

        # Non-finite
        assert ScoreNormalizer.normalize_bm25(float("nan")) == 0.0

    def test_normalize_rrf(self) -> None:
        # For k=60, num_sources=2: max_score = 2 / 61 ≈ 0.03278688
        k = 60
        num_sources = 2
        max_score = 2.0 / 61.0

        # Top 1 in both sources -> 1.0
        assert math.isclose(
            ScoreNormalizer.normalize_rrf(max_score, k=k, num_sources=num_sources),
            1.0,
            rel_tol=1e-5,
        )

        # Top 1 in only one source (1 / 61) -> 0.5
        assert math.isclose(
            ScoreNormalizer.normalize_rrf(1.0 / 61.0, k=k, num_sources=num_sources),
            0.5,
            rel_tol=1e-5,
        )

        # Zero or negative
        assert ScoreNormalizer.normalize_rrf(0.0) == 0.0
        assert ScoreNormalizer.normalize_rrf(-0.01) == 0.0
        assert ScoreNormalizer.normalize_rrf(float("nan")) == 0.0

    def test_normalize_reranker_scores(self) -> None:
        # Probability / normalized [0, 1]
        assert ScoreNormalizer.normalize_reranker(0.75) == 0.75
        assert ScoreNormalizer.normalize_reranker(1.5) == 1.0
        assert ScoreNormalizer.normalize_reranker(-0.5) == 0.0

        # Sigmoid for logits
        assert math.isclose(
            ScoreNormalizer.normalize_reranker(0.0, is_logit=True), 0.5, rel_tol=1e-5
        )
        assert ScoreNormalizer.normalize_reranker(10.0, is_logit=True) > 0.99
        assert ScoreNormalizer.normalize_reranker(-10.0, is_logit=True) < 0.01

    def test_aggregate_retrieval_empty_candidates(self) -> None:
        assert ScoreNormalizer.aggregate_retrieval_signal([]) == 0.0
        assert ScoreNormalizer.aggregate_reranking_signal([]) == 0.0

    def test_aggregate_retrieval_with_hybrid_candidate(self) -> None:
        # Candidate with RRF score equal to max theoretical (2 / 61)
        k = 60
        max_rrf = 2.0 / 61.0
        hybrid_cand = HybridRetrievalResult(
            chunk_id="chunk-1",
            content="test content",
            score=max_rrf,
            rrf_score=max_rrf,
            rank=1,
            dense_rank=1,
            bm25_rank=1,
            source_ranks={"dense": 1, "bm25": 1},
        )
        score = ScoreNormalizer.aggregate_retrieval_signal([hybrid_cand], k=k, num_sources=2)
        assert math.isclose(score, 1.0, rel_tol=1e-5)
