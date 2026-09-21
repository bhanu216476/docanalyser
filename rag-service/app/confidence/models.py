"""
Data models for RAG Confidence Scoring.

Defines:
- ConfidenceBand: Categorical descriptive confidence classification (HIGH, MEDIUM, LOW).
- AnswerabilityStatus: Deterministic assessment of evidence sufficiency (ANSWERABLE, PARTIALLY_ANSWERABLE, NOT_ANSWERABLE).
- ConfidenceSignals: Individual normalized signal components (each in [0.0, 1.0]).
- ConfidenceWeights: Configured linear combination weights for signals (sum to 1.0).
- ConfidenceResult: Structured explainable outcome with score, signals breakdown, weights, and bands.
"""

from __future__ import annotations

from enum import Enum
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfidenceBand(str, Enum):
    """
    Descriptive confidence classification for engineering diagnostics and UI cues.
    
    NOT a calibrated probability.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnswerabilityStatus(str, Enum):
    """
    Deterministic classification of evidence sufficiency for answering the query.
    """

    ANSWERABLE = "ANSWERABLE"
    PARTIALLY_ANSWERABLE = "PARTIALLY_ANSWERABLE"
    NOT_ANSWERABLE = "NOT_ANSWERABLE"


class ConfidenceSignals(BaseModel):
    """
    Normalized signal inputs for the confidence scoring formula.
    All signals must strictly reside in [0.0, 1.0].
    """

    retrieval: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized retrieval signal from dense/BM25/RRF candidates.",
    )
    reranking: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized reranker relevance signal.",
    )
    citation_support: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized claim-level citation verification support signal.",
    )
    answerability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized answerability assessment signal.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("retrieval", "reranking", "citation_support", "answerability")
    @classmethod
    def validate_signal_bounds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Signal must be in [0.0, 1.0], got {v}")
        return v


class ConfidenceWeights(BaseModel):
    """
    Configured linear weights applied to confidence signals.
    Must sum to 1.0 within numerical precision.
    """

    retrieval: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for retrieval signal.",
    )
    reranking: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for reranking signal.",
    )
    citation_support: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        alias="citation",
        description="Weight for citation support signal.",
    )
    answerability: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for answerability signal.",
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    @property
    def citation(self) -> float:
        """Alias for citation_support."""
        return self.citation_support

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> "ConfidenceWeights":
        total = self.retrieval + self.reranking + self.citation_support + self.answerability
        if not math.isclose(total, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError(f"Confidence weights must sum to 1.0, got {total:.4f}")
        return self


class ConfidenceResult(BaseModel):
    """
    Structured explainable result of the RAG Confidence Scoring calculation.

    Exposes both structured breakdowns (`signals`, `weights`) and direct
    convenience fields (`confidence`, `score`, `band`, `explanation`).
    """

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall weighted confidence score in [0.0, 1.0].",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Direct alias for confidence.",
    )
    signals: ConfidenceSignals = Field(
        ...,
        description="Individual normalized signal values in [0.0, 1.0].",
    )
    weights: ConfidenceWeights = Field(
        ...,
        description="Weights applied during score computation.",
    )
    band: ConfidenceBand = Field(
        ...,
        description="Engineering diagnostic band: HIGH, MEDIUM, or LOW.",
    )
    retrieval_signal: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for signals.retrieval.",
    )
    reranking_signal: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for signals.reranking.",
    )
    citation_support_signal: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for signals.citation_support.",
    )
    answerability_signal: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for signals.answerability.",
    )
    retrieval_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for weights.retrieval.",
    )
    reranking_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for weights.reranking.",
    )
    citation_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for weights.citation_support.",
    )
    answerability_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Convenience accessor for weights.answerability.",
    )
    explanation: str = Field(
        default="",
        description="Human-readable mathematical explanation of the confidence computation.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic metadata (e.g. claim counts, raw scores, normalizer strategy).",
    )

    model_config = ConfigDict(frozen=True)
