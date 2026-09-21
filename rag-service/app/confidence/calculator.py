"""
Confidence Calculator for RAG Confidence Scoring.

Calculates a deterministic, explainable engineering confidence score
from normalized signals:
    Confidence =
        w_retrieval   × RetrievalSignal
      + w_reranking   × RerankingSignal
      + w_citation    × CitationSupportSignal
      + w_answer      × AnswerabilitySignal

Clamped strictly to [0.0, 1.0].
"""

from __future__ import annotations

import logging
from typing import Optional, Union

from app.confidence.models import (
    ConfidenceBand,
    ConfidenceResult,
    ConfidenceSignals,
    ConfidenceWeights,
)
from app.confidence.normalizer import ScoreNormalizer
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """
    Deterministic confidence calculation engine.
    """

    def __init__(
        self,
        weights: Optional[ConfidenceWeights] = None,
        high_threshold: Optional[float] = None,
        low_threshold: Optional[float] = None,
    ) -> None:
        """
        Initialize ConfidenceCalculator with configurable weights and band thresholds.

        If not provided, values are read from application settings.
        """
        if weights is not None:
            self.weights = weights
        else:
            self.weights = ConfidenceWeights(
                retrieval=settings.confidence_retrieval_weight,
                reranking=settings.confidence_reranking_weight,
                citation=settings.confidence_citation_weight,
                answerability=settings.confidence_answerability_weight,
            )

        self.high_threshold = (
            high_threshold
            if high_threshold is not None
            else settings.confidence_high_threshold
        )
        self.low_threshold = (
            low_threshold
            if low_threshold is not None
            else settings.confidence_low_threshold
        )

        if self.low_threshold > self.high_threshold:
            raise ValueError(
                f"low_threshold ({self.low_threshold}) cannot exceed "
                f"high_threshold ({self.high_threshold})"
            )

    def calculate(
        self,
        signals: Union[ConfidenceSignals, dict[str, float]],
        metadata: Optional[dict[str, object]] = None,
    ) -> ConfidenceResult:
        """
        Calculate weighted confidence score from input signals.

        Args:
            signals: ConfidenceSignals model or dict mapping signal names to floats.
            metadata: Optional diagnostic metadata to include in the result.

        Returns:
            ConfidenceResult containing score, breakdown, band, and explanation.
        """
        if isinstance(signals, dict):
            # Validate and convert dict
            retrieval_raw = signals.get("retrieval", 0.0)
            reranking_raw = signals.get("reranking", 0.0)
            citation_raw = signals.get("citation_support", signals.get("citation", 0.0))
            answerability_raw = signals.get("answerability", 0.0)

            # Clamp signals to [0.0, 1.0]
            signals = ConfidenceSignals(
                retrieval=ScoreNormalizer.clamp(retrieval_raw, 0.0, 1.0),
                reranking=ScoreNormalizer.clamp(reranking_raw, 0.0, 1.0),
                citation_support=ScoreNormalizer.clamp(citation_raw, 0.0, 1.0),
                answerability=ScoreNormalizer.clamp(answerability_raw, 0.0, 1.0),
            )

        # Mathematical weighted sum
        raw_score = (
            self.weights.retrieval * signals.retrieval
            + self.weights.reranking * signals.reranking
            + self.weights.citation_support * signals.citation_support
            + self.weights.answerability * signals.answerability
        )

        # Enforce strict bounds [0.0, 1.0]
        final_score = ScoreNormalizer.clamp(raw_score, 0.0, 1.0)
        # Round to 4 decimal places for clean floating precision
        final_score = round(final_score, 4)

        # Classify descriptive diagnostic band
        if final_score >= self.high_threshold:
            band = ConfidenceBand.HIGH
        elif final_score >= self.low_threshold:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        # Generate human-readable mathematical explanation
        explanation = (
            f"Confidence: {final_score:.4f} = "
            f"{self.weights.retrieval:.2f}×{signals.retrieval:.4f} (retrieval) + "
            f"{self.weights.reranking:.2f}×{signals.reranking:.4f} (reranking) + "
            f"{self.weights.citation_support:.2f}×{signals.citation_support:.4f} (citation) + "
            f"{self.weights.answerability:.2f}×{signals.answerability:.4f} (answerability)"
        )

        return ConfidenceResult(
            confidence=final_score,
            score=final_score,
            signals=signals,
            weights=self.weights,
            band=band,
            retrieval_signal=signals.retrieval,
            reranking_signal=signals.reranking,
            citation_support_signal=signals.citation_support,
            answerability_signal=signals.answerability,
            retrieval_weight=self.weights.retrieval,
            reranking_weight=self.weights.reranking,
            citation_weight=self.weights.citation_support,
            answerability_weight=self.weights.answerability,
            explanation=explanation,
            metadata=dict(metadata or {}),
        )
