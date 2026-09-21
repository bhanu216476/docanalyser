"""
Unit tests for ConfidenceCalculator covering all mandatory test cases from Section 12.
"""

import math
import pytest

from app.confidence.calculator import ConfidenceCalculator
from app.confidence.models import (
    ConfidenceBand,
    ConfidenceSignals,
    ConfidenceWeights,
)
from app.confidence.signals import calculate_citation_support_signal
from app.verification.models import (
    ClaimVerificationResult,
    VerificationResult,
    VerificationStatus,
)


class TestConfidenceCalculator:
    # ------------------------------------------------------------------
    # Test 1 — Perfect confidence
    # ------------------------------------------------------------------
    def test_perfect_confidence(self) -> None:
        calc = ConfidenceCalculator()
        signals = ConfidenceSignals(
            retrieval=1.0,
            reranking=1.0,
            citation_support=1.0,
            answerability=1.0,
        )
        res = calc.calculate(signals)
        assert res.confidence == 1.0
        assert res.score == 1.0
        assert res.band == ConfidenceBand.HIGH

    # ------------------------------------------------------------------
    # Test 2 — Zero confidence
    # ------------------------------------------------------------------
    def test_zero_confidence(self) -> None:
        calc = ConfidenceCalculator()
        signals = ConfidenceSignals(
            retrieval=0.0,
            reranking=0.0,
            citation_support=0.0,
            answerability=0.0,
        )
        res = calc.calculate(signals)
        assert res.confidence == 0.0
        assert res.score == 0.0
        assert res.band == ConfidenceBand.LOW

    # ------------------------------------------------------------------
    # Test 3 — Weighted calculation
    # ------------------------------------------------------------------
    def test_weighted_calculation(self) -> None:
        calc = ConfidenceCalculator()
        # retrieval = 0.90, reranking = 0.80, citation = 1.00, answerability = 0.90
        # 0.20 * 0.90 + 0.25 * 0.80 + 0.35 * 1.00 + 0.20 * 0.90
        # = 0.18 + 0.20 + 0.35 + 0.18 = 0.91
        signals = ConfidenceSignals(
            retrieval=0.90,
            reranking=0.80,
            citation_support=1.00,
            answerability=0.90,
        )
        res = calc.calculate(signals)
        assert res.confidence == 0.9100
        assert res.band == ConfidenceBand.HIGH
        assert res.signals.retrieval == 0.90
        assert res.signals.reranking == 0.80
        assert res.signals.citation_support == 1.00
        assert res.signals.answerability == 0.90
        assert "0.9100" in res.explanation

    # ------------------------------------------------------------------
    # Test 4 — Strong retrieval, weak citation
    # ------------------------------------------------------------------
    def test_strong_retrieval_weak_citation(self) -> None:
        calc = ConfidenceCalculator()
        signals = ConfidenceSignals(
            retrieval=1.0,
            reranking=1.0,
            citation_support=0.0,
            answerability=0.5,
        )
        # 0.20(1.0) + 0.25(1.0) + 0.35(0.0) + 0.20(0.5) = 0.20 + 0.25 + 0.0 + 0.10 = 0.55
        res = calc.calculate(signals)
        assert res.confidence == 0.5500
        assert res.band == ConfidenceBand.MEDIUM
        assert res.confidence < 0.60

    # ------------------------------------------------------------------
    # Test 5 — Strong reranking, unsupported claim
    # ------------------------------------------------------------------
    def test_strong_reranking_unsupported_claim(self) -> None:
        calc = ConfidenceCalculator()
        signals = ConfidenceSignals(
            retrieval=0.80,
            reranking=1.00,
            citation_support=0.00,
            answerability=0.00,
        )
        # 0.20(0.80) + 0.25(1.00) + 0.35(0.00) + 0.20(0.00) = 0.16 + 0.25 = 0.41
        res = calc.calculate(signals)
        assert res.confidence == 0.4100
        assert res.band == ConfidenceBand.LOW

    # ------------------------------------------------------------------
    # Test 6 — Uncertain evidence
    # ------------------------------------------------------------------
    def test_uncertain_evidence_citation_support(self) -> None:
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNCERTAIN,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Conflicting evidence claim",
                    citation_ids=[1],
                    status=VerificationStatus.UNCERTAIN,
                )
            ],
            total_claims=1,
            uncertain_count=1,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer with [1]")
        assert support == 0.5

    # ------------------------------------------------------------------
    # Test 7 — Uncited factual answer
    # ------------------------------------------------------------------
    def test_uncited_factual_answer_reduces_support(self) -> None:
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNCITED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Factual claim without citation",
                    citation_ids=[],
                    status=VerificationStatus.UNCITED,
                )
            ],
            total_claims=1,
            uncited_count=1,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer without citation.")
        assert support == 0.0

    # ------------------------------------------------------------------
    # Test 8 — Multiple claims
    # ------------------------------------------------------------------
    def test_multiple_claims_support_calculation(self) -> None:
        # SUPPORTED (1.0), SUPPORTED (1.0), UNCERTAIN (0.5), UNSUPPORTED (0.0)
        # (1.0 + 1.0 + 0.5 + 0.0) / 4 = 2.5 / 4 = 0.625
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNSUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Claim 1",
                    citation_ids=[1],
                    status=VerificationStatus.SUPPORTED,
                ),
                ClaimVerificationResult(
                    claim_id=2,
                    claim="Claim 2",
                    citation_ids=[2],
                    status=VerificationStatus.SUPPORTED,
                ),
                ClaimVerificationResult(
                    claim_id=3,
                    claim="Claim 3",
                    citation_ids=[3],
                    status=VerificationStatus.UNCERTAIN,
                ),
                ClaimVerificationResult(
                    claim_id=4,
                    claim="Claim 4",
                    citation_ids=[4],
                    status=VerificationStatus.UNSUPPORTED,
                ),
            ],
            total_claims=4,
            supported_count=2,
            uncertain_count=1,
            unsupported_count=1,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer with 4 claims.")
        assert support == 0.625

    # ------------------------------------------------------------------
    # Test 9 — Invalid weights
    # ------------------------------------------------------------------
    def test_invalid_weights_rejected(self) -> None:
        # Sum != 1.0
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ConfidenceWeights(
                retrieval=0.3,
                reranking=0.3,
                citation=0.3,
                answerability=0.3,
            )

        # Negative weight
        with pytest.raises(ValueError):
            ConfidenceWeights(
                retrieval=-0.2,
                reranking=0.45,
                citation=0.45,
                answerability=0.3,
            )

    # ------------------------------------------------------------------
    # Test 10 — Score bounds
    # ------------------------------------------------------------------
    def test_score_bounds(self) -> None:
        calc = ConfidenceCalculator()
        # Test signals passed as dict with values below 0 and above 1
        res = calc.calculate(
            {
                "retrieval": 1.5,
                "reranking": -0.2,
                "citation": 1.2,
                "answerability": 2.0,
            }
        )
        assert 0.0 <= res.confidence <= 1.0
        assert res.signals.retrieval == 1.0
        assert res.signals.reranking == 0.0
        assert res.signals.citation_support == 1.0
        assert res.signals.answerability == 1.0

    # ------------------------------------------------------------------
    # Test 11 — Determinism
    # ------------------------------------------------------------------
    def test_determinism(self) -> None:
        calc = ConfidenceCalculator()
        signals = ConfidenceSignals(
            retrieval=0.7321,
            reranking=0.8142,
            citation_support=0.6667,
            answerability=0.5000,
        )
        res1 = calc.calculate(signals)
        res2 = calc.calculate(signals)
        res3 = calc.calculate(signals)

        assert res1.confidence == res2.confidence == res3.confidence
        assert res1.explanation == res2.explanation == res3.explanation
        assert res1.model_dump() == res2.model_dump() == res3.model_dump()
