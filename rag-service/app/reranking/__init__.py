"""
Reranking package — experiment framework for evaluating candidate rerankers.

Public API
----------
Protocols / abstractions:
    Reranker
    BaseReranker

Implementations:
    MockReranker

Pipeline:
    RerankedPipeline

Experiment framework:
    RerankingExperimentFramework

Models:
    RerankedResult
    RerankRequest
    RankingChangeMetrics
    LatencyMetrics
    RerankExperimentResult
    RerankExperimentBatchReport

Metrics:
    compute_ranking_metrics
"""

from __future__ import annotations

from app.reranking.base import BaseReranker, Reranker
from app.reranking.experiment import RerankingExperimentFramework
from app.reranking.metrics import compute_latency, compute_ranking_metrics
from app.reranking.mock_reranker import MockReranker
from app.reranking.models import (
    LatencyMetrics,
    RankingChangeMetrics,
    RerankExperimentBatchReport,
    RerankExperimentResult,
    RerankRequest,
    RerankedResult,
)
from app.reranking.pipeline import RerankedPipeline

__all__ = [
    # Protocols / abstractions
    "Reranker",
    "BaseReranker",
    # Implementations
    "MockReranker",
    # Pipeline
    "RerankedPipeline",
    # Experiment framework
    "RerankingExperimentFramework",
    # Models
    "RerankedResult",
    "RerankRequest",
    "RankingChangeMetrics",
    "LatencyMetrics",
    "RerankExperimentResult",
    "RerankExperimentBatchReport",
    # Metrics
    "compute_latency",
    "compute_ranking_metrics",
]
