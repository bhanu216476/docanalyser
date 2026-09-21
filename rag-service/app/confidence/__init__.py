"""
DocAnalyser Confidence Scoring Module.

Provides explainable, transparent, and deterministic confidence scoring
for the DocAnalyser RAG pipeline.
"""

from app.confidence.answerability import AnswerabilityEvaluator
from app.confidence.calculator import ConfidenceCalculator
from app.confidence.models import (
    AnswerabilityStatus,
    ConfidenceBand,
    ConfidenceResult,
    ConfidenceSignals,
    ConfidenceWeights,
)
from app.confidence.normalizer import ScoreNormalizer
from app.confidence.signals import SignalExtractor, calculate_citation_support_signal

__all__ = [
    "AnswerabilityEvaluator",
    "AnswerabilityStatus",
    "ConfidenceBand",
    "ConfidenceCalculator",
    "ConfidenceResult",
    "ConfidenceSignals",
    "ConfidenceWeights",
    "ScoreNormalizer",
    "SignalExtractor",
    "calculate_citation_support_signal",
]
