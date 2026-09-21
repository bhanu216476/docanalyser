"""
Score Normalization Service for RAG Confidence Scoring.

Different retrieval algorithms (Dense embeddings, BM25 lexical, RRF fusion)
and reranking mechanisms produce raw scores on fundamentally incompatible scales:
- Dense Cosine Similarity: [-1.0, 1.0], typically [0.0, 1.0] for positive semantic embeddings.
- BM25 Lexical Score: [0.0, +∞), unbounded term-frequency saturation.
- Reciprocal Rank Fusion (RRF): [0.0, M / (k + 1)], small fractional sum of reciprocal ranks.
- Reranker Scores: [0.0, 1.0] for normalized models/mocks, or (-∞, +∞) for raw logits.

ScoreNormalizer guarantees that all scores are deterministically transformed
into standard [0.0, 1.0] signals without silently mixing incompatible scales.
"""

from __future__ import annotations

import logging
import math
from typing import Optional, Sequence, Union

from app.reranking.models import RerankedResult
from app.retrieval.models import HybridRetrievalResult, RetrievalResult

logger = logging.getLogger(__name__)


class ScoreNormalizer:
    """
    Normalizes heterogeneous retrieval and reranking scores into [0.0, 1.0].
    """

    @staticmethod
    def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Clamp a numeric value strictly within [min_val, max_val]."""
        if not math.isfinite(value):
            return min_val
        return max(min_val, min(max_val, float(value)))

    @classmethod
    def normalize_cosine(
        cls,
        score: float,
        allow_negative: bool = False,
    ) -> float:
        """
        Normalize a cosine similarity score to [0.0, 1.0].

        Args:
            score: Raw cosine similarity.
            allow_negative: If True, maps [-1.0, 1.0] linearly to [0.0, 1.0]
                            via (score + 1.0) / 2.0. If False, assumes non-negative
                            semantic similarity and clamps [0.0, 1.0].
        """
        if not math.isfinite(score):
            return 0.0
        if allow_negative:
            return cls.clamp((score + 1.0) / 2.0, 0.0, 1.0)
        return cls.clamp(score, 0.0, 1.0)

    @classmethod
    def normalize_bm25(
        cls,
        score: float,
        k_norm: float = 10.0,
    ) -> float:
        """
        Normalize an unbounded BM25 lexical score to [0.0, 1.0] using soft saturation.

        Formula:
            normalized = score / (score + k_norm) for score >= 0.0

        Args:
            score: Non-negative BM25 relevance score.
            k_norm: Half-saturation constant (default 10.0). When score == k_norm,
                    the normalized score is exactly 0.5.
        """
        if not math.isfinite(score) or score <= 0.0:
            return 0.0
        normalized = score / (score + max(1e-6, k_norm))
        return cls.clamp(normalized, 0.0, 1.0)

    @classmethod
    def normalize_rrf(
        cls,
        score: float,
        k: int = 60,
        num_sources: int = 2,
    ) -> float:
        """
        Normalize a Reciprocal Rank Fusion (RRF) score to [0.0, 1.0].

        In RRF:
            score = sum_{source} 1.0 / (k + rank_source)

        The theoretical maximum occurs when a document is ranked #1 in all `num_sources`:
            max_score = num_sources / (k + 1)

        Normalizing by max_score maps rank-1 items across all sources to 1.0.

        Args:
            score: Raw RRF score.
            k: RRF ranking constant (typically settings.rrf_k = 60).
            num_sources: Number of fused retrieval lists (typically 2: dense + bm25).
        """
        if not math.isfinite(score) or score <= 0.0:
            return 0.0
        max_possible = float(num_sources) / float(k + 1)
        if max_possible <= 0.0:
            return 0.0
        normalized = score / max_possible
        return cls.clamp(normalized, 0.0, 1.0)

    @classmethod
    def normalize_reranker(
        cls,
        score: float,
        is_logit: bool = False,
    ) -> float:
        """
        Normalize a candidate reranker score to [0.0, 1.0].

        Args:
            score: Reranker score (either [0.0, 1.0] or raw unbounded logit).
            is_logit: If True, applies standard logistic sigmoid function.
                      If False, treats as [0.0, 1.0] probability/score and clamps.
        """
        if not math.isfinite(score):
            return 0.0
        if is_logit:
            try:
                # Numerically stable sigmoid
                if score >= 0:
                    z = math.exp(-score)
                    return 1.0 / (1.0 + z)
                else:
                    z = math.exp(score)
                    return z / (1.0 + z)
            except OverflowError:
                return 1.0 if score > 0 else 0.0
        return cls.clamp(score, 0.0, 1.0)

    @classmethod
    def normalize_retrieval_candidate(
        cls,
        candidate: Union[RetrievalResult, HybridRetrievalResult, RerankedResult],
        k: int = 60,
        num_sources: int = 2,
    ) -> float:
        """
        Extract and normalize the retrieval score from a single candidate object.
        """
        if isinstance(candidate, HybridRetrievalResult):
            return cls.normalize_rrf(candidate.rrf_score, k=k, num_sources=num_sources)
        if isinstance(candidate, RerankedResult):
            # Check if retrieval_score appears to be RRF (typically < 0.1 for k=60)
            if hasattr(candidate, "source_ranks") and candidate.source_ranks:
                return cls.normalize_rrf(candidate.retrieval_score, k=k, num_sources=len(candidate.source_ranks))
            if candidate.dense_rank is not None or candidate.bm25_rank is not None:
                return cls.normalize_rrf(candidate.retrieval_score, k=k, num_sources=num_sources)
            return cls.normalize_cosine(candidate.retrieval_score)
        if isinstance(candidate, RetrievalResult):
            return cls.normalize_cosine(candidate.score)
        return 0.0

    @classmethod
    def aggregate_retrieval_signal(
        cls,
        candidates: Sequence[Union[RetrievalResult, HybridRetrievalResult, RerankedResult]],
        k: int = 60,
        num_sources: int = 2,
        strategy: str = "top1",
    ) -> float:
        """
        Compute an aggregate normalized retrieval signal from candidate items.

        Args:
            candidates: Sequence of retrieved candidates.
            k: RRF constant.
            num_sources: Number of fused sources.
            strategy: 'top1' (use top candidate score) or 'mean_top_k' (average of candidates).
        """
        if not candidates:
            return 0.0

        scores = [
            cls.normalize_retrieval_candidate(c, k=k, num_sources=num_sources)
            for c in candidates
        ]
        if not scores:
            return 0.0

        if strategy == "mean_top_k":
            return cls.clamp(sum(scores) / len(scores), 0.0, 1.0)
        # Default: top-1 candidate score
        return cls.clamp(scores[0], 0.0, 1.0)

    @classmethod
    def aggregate_reranking_signal(
        cls,
        candidates: Sequence[RerankedResult],
        is_logit: bool = False,
        strategy: str = "top1",
    ) -> float:
        """
        Compute an aggregate normalized reranking signal from reranked candidates.

        Args:
            candidates: Sequence of reranked candidates.
            is_logit: Whether reranker scores are raw logits.
            strategy: 'top1' (use top candidate score) or 'mean_top_k'.
        """
        if not candidates:
            return 0.0

        scores = [
            cls.normalize_reranker(c.reranker_score, is_logit=is_logit)
            for c in candidates
        ]
        if not scores:
            return 0.0

        if strategy == "mean_top_k":
            return cls.clamp(sum(scores) / len(scores), 0.0, 1.0)
        # Default: top-1 candidate score
        return cls.clamp(scores[0], 0.0, 1.0)
