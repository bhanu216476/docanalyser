from __future__ import annotations

import math
from typing import Sequence

from app.verification.models import VerificationResult, VerificationStatus


def compute_retrieval_metrics(
    *,
    retrieved_ids: Sequence[str] | None,
    relevant_ids: Sequence[str] | None,
    k: int | None = None,
) -> dict[str, float | None]:
    """Compute hit rate, recall, precision, and MRR for a retrieved list."""
    retrieved = list(retrieved_ids or [])
    relevant = list(relevant_ids or [])
    if not relevant:
        return {
            "hit_rate_at_k": None,
            "recall_at_k": None,
            "precision_at_k": None,
            "mrr": None,
        }

    top_k = max(1, int(k)) if k is not None else len(retrieved)
    if top_k <= 0:
        top_k = len(retrieved) or 1
    top = retrieved[:top_k]
    relevant_set = set(relevant)
    relevant_retrieved = len(set(top) & relevant_set)
    hit_rate_at_k = 1.0 if relevant_retrieved > 0 else 0.0
    recall_at_k = relevant_retrieved / len(relevant_set)
    precision_at_k = relevant_retrieved / len(top) if top else 0.0

    reciprocal_rank = 0.0
    for rank, candidate in enumerate(top, start=1):
        if candidate in relevant_set:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "hit_rate_at_k": hit_rate_at_k,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "mrr": reciprocal_rank,
    }


def compute_grounding_metrics(
    verification: VerificationResult | None,
) -> dict[str, float | int | dict[str, int] | None]:
    """Compute grounding metrics using the existing verification model."""
    if verification is None:
        return {
            "unsupported_claim_rate": None,
            "citation_coverage": None,
            "citation_correctness": None,
            "verification_status_distribution": {
                "SUPPORTED": 0,
                "UNSUPPORTED": 0,
                "UNCERTAIN": 0,
                "UNCITED": 0,
                "INVALID_CITATION": 0,
            },
        }

    distribution = {
        "SUPPORTED": verification.supported_count,
        "UNSUPPORTED": verification.unsupported_count,
        "UNCERTAIN": verification.uncertain_count,
        "UNCITED": verification.uncited_count,
        "INVALID_CITATION": verification.invalid_citation_count,
    }

    total_claims = verification.total_claims or len(verification.claims)
    unsupported_claim_rate = (
        verification.unsupported_count / total_claims if total_claims > 0 else None
    )
    cited_claims = total_claims - verification.uncited_count
    citation_coverage = (
        cited_claims / total_claims if total_claims > 0 else None
    )

    supported_cited_claims = 0
    for claim in verification.claims:
        if claim.citation_ids:
            if claim.status == VerificationStatus.SUPPORTED:
                supported_cited_claims += 1
    citation_correctness = (
        supported_cited_claims / max(1, cited_claims) if cited_claims > 0 else None
    )

    return {
        "unsupported_claim_rate": unsupported_claim_rate,
        "citation_coverage": citation_coverage,
        "citation_correctness": citation_correctness,
        "verification_status_distribution": distribution,
    }


def compute_decision_metrics(
    *,
    total_questions: int,
    answered_questions: int,
    refused_questions: int,
    correct_refusal: int | None = None,
    incorrect_refusal: int | None = None,
    correct_answer: int | None = None,
    incorrect_answer: int | None = None,
) -> dict[str, float | int | None]:
    """Compute answered/refused statistics and optional correctness breakdown."""
    refusal_rate = (
        refused_questions / total_questions if total_questions > 0 else None
    )
    metrics = {
        "total_questions": total_questions,
        "answered_count": answered_questions,
        "refused_count": refused_questions,
        "refusal_rate": refusal_rate,
        "correct_refusal": correct_refusal,
        "incorrect_refusal": incorrect_refusal,
        "correct_answer": correct_answer,
        "incorrect_answer": incorrect_answer,
    }
    return metrics


def compute_latency_stats(latencies: Sequence[float]) -> dict[str, float]:
    """Compute average, median, and p95 latency in milliseconds."""
    values = [float(v) for v in latencies]
    if not values:
        return {
            "average_total_latency_ms": 0.0,
            "median_total_latency_ms": 0.0,
            "p95_total_latency_ms": 0.0,
        }

    sorted_values = sorted(values)
    average = sum(sorted_values) / len(sorted_values)
    median = _median(sorted_values)
    p95 = _percentile(sorted_values, 95)
    return {
        "average_total_latency_ms": average,
        "median_total_latency_ms": median,
        "p95_total_latency_ms": p95,
    }


def _median(values: Sequence[float]) -> float:
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return float((values[mid - 1] + values[mid]) / 2.0)


def _percentile(values: Sequence[float], percentile: float) -> float:
    if len(values) == 1:
        return float(values[0])
    if percentile <= 0:
        return float(values[0])
    if percentile >= 100:
        return float(values[-1])
    fraction = (percentile / 100.0) * (len(values) - 1)
    lower = math.floor(fraction)
    upper = math.ceil(fraction)
    if lower == upper:
        return float(values[lower])
    weight = fraction - lower
    left = values[lower]
    right = values[upper]
    return float(left + (right - left) * weight)
