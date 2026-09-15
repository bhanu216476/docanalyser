"""
Data models for the Reranker interface, results, and experiment framework.

Preserves separate retrieval and reranking scores, tracks rank deltas,
and captures high-resolution latency and ranking shift metrics.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.retrieval.models import RetrievalProvenance, RetrievalResult


class RerankedResult(BaseModel):
    """
    Reranked document chunk result.

    Preserves both the pre-reranking retrieval score and the post-reranking
    reranker score, along with initial and updated rank positions.
    """

    chunk_id: str = Field(
        ...,
        min_length=1,
        description="Deterministic chunk identifier.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the chunk.",
    )
    retrieval_score: float = Field(
        ...,
        description="Pre-reranking score (e.g. RRF score or similarity score).",
    )
    reranker_score: float = Field(
        ...,
        description="Score assigned by the reranker model/provider.",
    )
    retrieval_rank: int = Field(
        ...,
        ge=1,
        description="1-based rank before reranking.",
    )
    reranked_rank: int = Field(
        ...,
        ge=1,
        description="1-based rank after reranking.",
    )
    rank_delta: int = Field(
        ...,
        description=(
            "Change in rank position (retrieval_rank - reranked_rank). "
            ">0 indicates promotion, <0 indicates demotion, 0 is unchanged."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom chunk metadata.",
    )
    document_id: str = Field(default="", description="Source document identifier.")
    chunk_index: Optional[int] = Field(
        default=None, ge=0, description="0-based sequential index within document."
    )
    file_name: str = Field(default="", description="Basename of source file.")
    file_type: str = Field(default="", description="File extension.")
    source: str = Field(default="", description="Source location.")
    section: Optional[str] = Field(default=None, description="Markdown section.")
    provenance: Optional[RetrievalProvenance] = None
    dense_rank: Optional[int] = Field(
        default=None, ge=1, description="Original dense rank if from hybrid retrieval."
    )
    bm25_rank: Optional[int] = Field(
        default=None, ge=1, description="Original BM25 rank if from hybrid retrieval."
    )
    source_ranks: dict[str, int] = Field(
        default_factory=dict,
        description="Per-source rank breakdown from previous retrieval stages.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("retrieval_score", "reranker_score")
    @classmethod
    def validate_finite_scores(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Scores must be finite numbers")
        return value


class RerankRequest(BaseModel):
    """Request payload for candidate reranking."""

    query: str = Field(
        ...,
        min_length=1,
        description="User query string.",
    )
    documents: list[RetrievalResult] = Field(
        ...,
        description="Candidate chunks to be reranked.",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional maximum number of reranked results to retain.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("query", mode="before")
    @classmethod
    def strip_and_validate_query(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("query cannot be empty or whitespace-only")
        return value.strip()


class RankingChangeMetrics(BaseModel):
    """Statistical summary of ranking changes caused by reranking."""

    mean_rank_displacement: float = Field(
        ...,
        ge=0.0,
        description="Average absolute rank displacement: sum(|r_old - r_new|) / N.",
    )
    top_1_changed: bool = Field(
        ...,
        description="Whether the #1 ranked document changed after reranking.",
    )
    top_k_overlap_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Jaccard overlap between pre-rerank top-K and post-rerank top-K sets.",
    )
    spearman_correlation: Optional[float] = Field(
        default=None,
        description="Spearman rank correlation coefficient between initial and reranked ranks.",
    )
    promoted_count: int = Field(
        ..., ge=0, description="Count of documents that improved their rank position."
    )
    demoted_count: int = Field(
        ..., ge=0, description="Count of documents that worsened their rank position."
    )
    unchanged_count: int = Field(
        ..., ge=0, description="Count of documents with identical rank before and after."
    )

    model_config = ConfigDict(frozen=True)


class LatencyMetrics(BaseModel):
    """High-resolution latency measurements for pipeline stages."""

    retrieval_latency_ms: float = Field(
        ..., ge=0.0, description="Candidate retrieval stage latency in ms."
    )
    reranking_latency_ms: float = Field(
        ..., ge=0.0, description="Reranking stage latency in ms."
    )
    total_latency_ms: float = Field(
        ..., ge=0.0, description="Total pipeline latency in ms."
    )

    model_config = ConfigDict(frozen=True)


class RerankExperimentResult(BaseModel):
    """Detailed evaluation result for a single query."""

    query: str = Field(..., description="Query evaluated.")
    candidate_count: int = Field(..., ge=0, description="Number of candidate chunks evaluated.")
    initial_results: list[RetrievalResult] = Field(
        default_factory=list, description="Top candidates before reranking."
    )
    reranked_results: list[RerankedResult] = Field(
        default_factory=list, description="Ranked candidates after reranking."
    )
    latency: LatencyMetrics = Field(..., description="Latency profile.")
    ranking_metrics: RankingChangeMetrics = Field(
        ..., description="Quantitative ranking shift metrics."
    )

    model_config = ConfigDict(frozen=True)


class RerankExperimentBatchReport(BaseModel):
    """Summary metrics across a batch of experiment queries."""

    total_queries: int = Field(..., ge=0, description="Total queries evaluated.")
    mean_retrieval_latency_ms: float = Field(..., ge=0.0)
    mean_reranking_latency_ms: float = Field(..., ge=0.0)
    mean_total_latency_ms: float = Field(..., ge=0.0)
    mean_rank_displacement: float = Field(..., ge=0.0)
    top_1_change_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of queries where top-1 changed."
    )
    mean_top_k_overlap_ratio: float = Field(..., ge=0.0, le=1.0)
    mean_spearman_correlation: Optional[float] = None
    query_results: list[RerankExperimentResult] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
