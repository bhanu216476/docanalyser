"""
Unit tests for AnswerabilityEvaluator.
"""

import pytest

from app.confidence.answerability import AnswerabilityEvaluator
from app.confidence.models import AnswerabilityStatus
from app.retrieval.models import RetrievalResult
from app.verification.models import (
    ClaimVerificationResult,
    VerificationResult,
    VerificationStatus,
)


def make_dummy_chunk(chunk_id: str = "c1") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content="Evidence content",
        score=0.9,
    )


class TestAnswerabilityEvaluator:
    def test_empty_query_or_answer(self) -> None:
        chunk = make_dummy_chunk()
        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="",
            answer="Valid answer",
            evidence_chunks=[chunk],
        )
        assert status == AnswerabilityStatus.NOT_ANSWERABLE
        assert score == 0.0

        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="Valid query",
            answer="",
            evidence_chunks=[chunk],
        )
        assert status == AnswerabilityStatus.NOT_ANSWERABLE
        assert score == 0.0

    def test_empty_evidence_chunks(self) -> None:
        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="Valid query",
            answer="Valid answer",
            evidence_chunks=[],
        )
        assert status == AnswerabilityStatus.NOT_ANSWERABLE
        assert score == 0.0

    def test_refusal_answer_detected(self) -> None:
        chunk = make_dummy_chunk()
        refusals = [
            "I do not have enough information to answer this question.",
            "The provided context does not contain details about leave policy.",
            "I cannot answer this question based on the provided documents.",
            "Leave details are not mentioned in the provided document.",
        ]
        for ref in refusals:
            status, score, _ = AnswerabilityEvaluator.evaluate(
                query="How many days?",
                answer=ref,
                evidence_chunks=[chunk],
            )
            assert status == AnswerabilityStatus.NOT_ANSWERABLE
            assert score == 0.0

    def test_all_claims_supported(self) -> None:
        chunk = make_dummy_chunk()
        v_result = VerificationResult(
            overall_status=VerificationStatus.SUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Leave is 12 days",
                    citation_ids=[1],
                    status=VerificationStatus.SUPPORTED,
                ),
            ],
            total_claims=1,
            supported_count=1,
        )
        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="How many days?",
            answer="Employees receive 12 days [1].",
            evidence_chunks=[chunk],
            verification_result=v_result,
        )
        assert status == AnswerabilityStatus.ANSWERABLE
        assert score == 1.0

    def test_all_claims_unsupported(self) -> None:
        chunk = make_dummy_chunk()
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNSUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Leave is 50 days",
                    citation_ids=[1],
                    status=VerificationStatus.UNSUPPORTED,
                ),
            ],
            total_claims=1,
            unsupported_count=1,
        )
        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="How many days?",
            answer="Employees receive 50 days [1].",
            evidence_chunks=[chunk],
            verification_result=v_result,
        )
        assert status == AnswerabilityStatus.NOT_ANSWERABLE
        assert score == 0.0

    def test_mixed_claims_partial_answerability(self) -> None:
        chunk = make_dummy_chunk()
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNSUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Leave is 12 days",
                    citation_ids=[1],
                    status=VerificationStatus.SUPPORTED,
                ),
                ClaimVerificationResult(
                    claim_id=2,
                    claim="Bonus is 50%",
                    citation_ids=[2],
                    status=VerificationStatus.UNSUPPORTED,
                ),
            ],
            total_claims=2,
            supported_count=1,
            unsupported_count=1,
        )
        status, score, _ = AnswerabilityEvaluator.evaluate(
            query="What are the benefits?",
            answer="Leave is 12 days [1]. Bonus is 50% [2].",
            evidence_chunks=[chunk],
            verification_result=v_result,
        )
        assert status == AnswerabilityStatus.PARTIALLY_ANSWERABLE
        assert score == 0.5
