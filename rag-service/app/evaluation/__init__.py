"""Automated evaluation tooling for the IntelliResearch RAG system."""

from app.evaluation.dataset import EvaluationCase, load_evaluation_dataset
from app.evaluation.metrics import (
    compute_decision_metrics,
    compute_grounding_metrics,
    compute_latency_stats,
    compute_retrieval_metrics,
)
from app.evaluation.models import EvaluationRecord, EvaluationReport
from app.evaluation.runner import EvaluationRunner

__all__ = [
    "EvaluationCase",
    "EvaluationRecord",
    "EvaluationReport",
    "EvaluationRunner",
    "compute_decision_metrics",
    "compute_grounding_metrics",
    "compute_latency_stats",
    "compute_retrieval_metrics",
    "load_evaluation_dataset",
]
