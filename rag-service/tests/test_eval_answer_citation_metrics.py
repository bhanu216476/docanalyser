"""
Unit tests for answer correctness, citation accuracy, no-answer evaluation,
faithfulness, and latency statistics.
"""

from __future__ import annotations

import pytest

from app.verification.models import (
    Claim,
    ClaimVerificationResult,
    VerificationPolicy,
    VerificationResult,
    VerificationStatus,
)
from evals.metrics.answer import evaluate_answer_correctness
from evals.metrics.citation import evaluate_citation_metrics
from evals.metrics.faithfulness import evaluate_faithfulness
from evals.metrics.latency import compute_latency_stats
from evals.metrics.no_answer import evaluate_no_answer, is_abstention


def test_citation_accuracy_correct_citation() -> None:
    generated = ["c1", "c2"]
    expected = {"c1", "c2"}
    precision, recall, accuracy = evaluate_citation_metrics(generated, expected)
    assert precision == 1.0
    assert recall == 1.0
    assert accuracy == 1.0


def test_citation_accuracy_wrong_citation() -> None:
    generated = ["wrong_chunk_1", "wrong_chunk_2"]
    expected = {"c1", "c2"}
    precision, recall, accuracy = evaluate_citation_metrics(generated, expected)
    assert precision == 0.0
    assert recall == 0.0
    assert accuracy == 0.0


def test_citation_accuracy_missing_citation() -> None:
    # Only generated c1, expected c1 and c2
    generated = ["c1"]
    expected = {"c1", "c2"}
    precision, recall, accuracy = evaluate_citation_metrics(generated, expected)
    assert precision == 1.0
    assert recall == 0.5
    assert accuracy == 0.5


def test_citation_accuracy_extra_citation() -> None:
    # Generated c1, c2, c3; expected only c1, c2
    generated = ["c1", "c2", "c3"]
    expected = {"c1", "c2"}
    precision, recall, accuracy = evaluate_citation_metrics(generated, expected)
    assert precision == pytest.approx(2.0 / 3.0, rel=1e-3)
    assert recall == 1.0
    assert accuracy == pytest.approx(2.0 / 3.0, rel=1e-3)


def test_no_answer_correct_abstention() -> None:
    refusal_answer = (
        "The provided documents do not contain sufficient information regarding this."
    )
    is_corr, score = evaluate_no_answer(refusal_answer, answerable=False)
    assert is_corr is True
    assert score == 1.0
    assert is_abstention(refusal_answer) is True


def test_no_answer_hallucinated_answer() -> None:
    hallucinated_answer = (
        "The lunar travel reimbursement limit is 50,000 dollars per trip."
    )
    is_corr, score = evaluate_no_answer(hallucinated_answer, answerable=False)
    assert is_corr is False
    assert score == 0.0
    assert is_abstention(hallucinated_answer) is False


def test_answer_correctness_exact_and_f1() -> None:
    # Exact substring
    gt = "12 casual leave days"
    gen = "Employees receive 12 casual leave days annually."
    assert evaluate_answer_correctness(gen, gt, answerable=True) == 1.0

    # Overlapping token match
    gt2 = "FastAPI endpoints return standard JSON responses."
    gen2 = "All FastAPI endpoints will return JSON responses to callers."
    score = evaluate_answer_correctness(gen2, gt2, answerable=True)
    assert score > 0.6


def test_faithfulness_evaluation() -> None:
    # Supported claims
    res1 = ClaimVerificationResult(
        claim_id=1,
        claim="Text 1",
        citation_ids=[1],
        status=VerificationStatus.SUPPORTED,
        reason="Supported by chunk",
    )
    v_res = VerificationResult.aggregate("Answer text", [res1])
    assert evaluate_faithfulness(v_res, answerable=True) == 1.0

    # Unsupported claims
    res2 = ClaimVerificationResult(
        claim_id=1,
        claim="Text 1",
        citation_ids=[1],
        status=VerificationStatus.UNSUPPORTED,
        reason="Contradicts chunk",
    )
    v_res_bad = VerificationResult.aggregate("Answer text", [res2])
    assert evaluate_faithfulness(v_res_bad, answerable=True) == 0.0


def test_latency_aggregation() -> None:
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    stats = compute_latency_stats(latencies)

    assert stats["count"] == 10.0
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 100.0
    assert stats["mean_ms"] == 55.0
    assert stats["median_ms"] == 55.0
    # 95th percentile of 10..100
    assert stats["p95_ms"] >= 90.0
