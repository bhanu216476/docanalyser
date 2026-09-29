import pytest

from app.evaluation.metrics import (
    compute_decision_metrics,
    compute_grounding_metrics,
    compute_latency_stats,
    compute_retrieval_metrics,
)
from app.verification.models import ClaimVerificationResult, VerificationResult, VerificationStatus


def test_retrieval_hit_rate_recall_precision_and_mrr() -> None:
    metrics = compute_retrieval_metrics(
        retrieved_ids=["chunk-3", "chunk-1", "chunk-9"],
        relevant_ids=["chunk-1", "chunk-7"],
        k=3,
    )

    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["recall_at_k"] == 0.5
    assert metrics["precision_at_k"] == pytest.approx(1 / 3)
    assert metrics["mrr"] == 1 / 2


def test_zero_ground_truth_returns_none() -> None:
    metrics = compute_retrieval_metrics(retrieved_ids=["chunk-3"], relevant_ids=[], k=3)

    assert metrics["hit_rate_at_k"] is None
    assert metrics["recall_at_k"] is None
    assert metrics["precision_at_k"] is None
    assert metrics["mrr"] is None


def test_grounding_metrics_compute_from_verification_result() -> None:
    result = VerificationResult(
        overall_status=VerificationStatus.UNSUPPORTED,
        claims=[
            ClaimVerificationResult(
                claim_id=1,
                claim="Alpha",
                citation_ids=[1],
                status=VerificationStatus.SUPPORTED,
            ),
            ClaimVerificationResult(
                claim_id=2,
                claim="Beta",
                citation_ids=[1],
                status=VerificationStatus.UNSUPPORTED,
            ),
            ClaimVerificationResult(
                claim_id=3,
                claim="Gamma",
                citation_ids=[],
                status=VerificationStatus.UNCITED,
            ),
        ],
        total_claims=3,
        supported_count=1,
        unsupported_count=1,
        uncited_count=1,
    )

    metrics = compute_grounding_metrics(result)

    assert metrics["unsupported_claim_rate"] == pytest.approx(1 / 3)
    assert metrics["citation_coverage"] == pytest.approx(2 / 3)
    assert metrics["citation_correctness"] == pytest.approx(1 / 2)
    assert metrics["verification_status_distribution"]["SUPPORTED"] == 1
    assert metrics["verification_status_distribution"]["UNCITED"] == 1


def test_decision_and_latency_metrics() -> None:
    decision = compute_decision_metrics(
        total_questions=4,
        answered_questions=3,
        refused_questions=1,
    )
    assert decision["answered_count"] == 3
    assert decision["refused_count"] == 1
    assert decision["refusal_rate"] == pytest.approx(0.25)

    latency = compute_latency_stats([100.0, 200.0, 300.0, 400.0])
    assert latency["average_total_latency_ms"] == pytest.approx(250.0)
    assert latency["median_total_latency_ms"] == pytest.approx(250.0)
    assert latency["p95_total_latency_ms"] == pytest.approx(385.0)
