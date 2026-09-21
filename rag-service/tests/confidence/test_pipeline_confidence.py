"""
Integration and edge case tests for RAG pipeline Confidence Scoring.
"""

from pathlib import Path
import pytest

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
from app.pipeline.models import RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import RAGPipeline, create_rag_pipeline
from app.verification.models import (
    ClaimVerificationResult,
    VerificationResult,
    VerificationStatus,
)


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample_policy.txt"
    p.write_text(
        "Working hours are 9 AM to 5 PM Monday through Friday.\n"
        "Employees receive 12 casual leave days annually.\n"
        "Medical leave requires a doctor's certificate.\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def in_memory_pipeline() -> RAGPipeline:
    return create_rag_pipeline(in_memory=True)


class TestPipelineConfidenceIntegration:
    def test_pipeline_query_returns_confidence_and_verification(
        self,
        in_memory_pipeline: RAGPipeline,
        sample_text_file: Path,
    ) -> None:
        """Verify pipeline execution computes verified citations, verification, and confidence."""
        in_memory_pipeline.ingest(sample_text_file)

        response: RAGResponse = in_memory_pipeline.query("What are the working hours?")
        assert response.answer
        assert response.confidence is not None
        assert isinstance(response.confidence, ConfidenceResult)
        assert 0.0 <= response.confidence.confidence <= 1.0
        assert 0.0 <= response.confidence.score <= 1.0
        assert response.confidence.band in (
            ConfidenceBand.HIGH,
            ConfidenceBand.MEDIUM,
            ConfidenceBand.LOW,
        )
        assert response.verification is not None
        assert "confidence_scoring_ms" in response.latency_breakdown_ms
        assert "citation_verification_ms" in response.latency_breakdown_ms
        assert "confidence" in response.metadata
        assert "verification_status" in response.metadata


class TestConfidenceEdgeCases:
    # ------------------------------------------------------------------
    # Edge case 1: No retrieved documents / empty retrieval result
    # ------------------------------------------------------------------
    def test_no_retrieved_documents(self) -> None:
        signals = SignalExtractor.extract_signals(
            query="test query",
            answer="test answer",
            retrieval_candidates=[],
            reranked_candidates=[],
            verification_result=None,
        )
        assert signals.retrieval == 0.0
        assert signals.reranking == 0.0
        assert signals.answerability == 0.0

        calc = ConfidenceCalculator()
        result = calc.calculate(signals)
        assert result.confidence == 0.0
        assert result.band == ConfidenceBand.LOW

    # ------------------------------------------------------------------
    # Edge case 2: Empty answer / no answer generated
    # ------------------------------------------------------------------
    def test_empty_answer(self) -> None:
        signals = SignalExtractor.extract_signals(
            query="What are the working hours?",
            answer="",
            retrieval_candidates=[],
            reranked_candidates=[],
            verification_result=None,
        )
        assert signals.citation_support == 0.0
        assert signals.answerability == 0.0

    # ------------------------------------------------------------------
    # Edge case 3: Missing citation verification
    # ------------------------------------------------------------------
    def test_missing_citation_verification(self) -> None:
        support = calculate_citation_support_signal(
            verification_result=None,
            answer="Some answer",
        )
        assert support == 0.0

    # ------------------------------------------------------------------
    # Edge case 4: All claims unsupported
    # ------------------------------------------------------------------
    def test_all_claims_unsupported(self) -> None:
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNSUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="False claim 1",
                    citation_ids=[1],
                    status=VerificationStatus.UNSUPPORTED,
                ),
                ClaimVerificationResult(
                    claim_id=2,
                    claim="False claim 2",
                    citation_ids=[2],
                    status=VerificationStatus.UNSUPPORTED,
                ),
            ],
            total_claims=2,
            unsupported_count=2,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer text")
        assert support == 0.0

    # ------------------------------------------------------------------
    # Edge case 5: All claims supported
    # ------------------------------------------------------------------
    def test_all_claims_supported(self) -> None:
        v_result = VerificationResult(
            overall_status=VerificationStatus.SUPPORTED,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="True claim 1",
                    citation_ids=[1],
                    status=VerificationStatus.SUPPORTED,
                ),
                ClaimVerificationResult(
                    claim_id=2,
                    claim="True claim 2",
                    citation_ids=[2],
                    status=VerificationStatus.SUPPORTED,
                ),
            ],
            total_claims=2,
            supported_count=2,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer text")
        assert support == 1.0

    # ------------------------------------------------------------------
    # Edge case 6: Conflicting evidence (UNCERTAIN)
    # ------------------------------------------------------------------
    def test_conflicting_evidence_uncertain(self) -> None:
        v_result = VerificationResult(
            overall_status=VerificationStatus.UNCERTAIN,
            claims=[
                ClaimVerificationResult(
                    claim_id=1,
                    claim="Conflicting claim",
                    citation_ids=[1, 2],
                    status=VerificationStatus.UNCERTAIN,
                ),
            ],
            total_claims=1,
            uncertain_count=1,
        )
        support = calculate_citation_support_signal(v_result, answer="Answer text")
        assert support == 0.5

    # ------------------------------------------------------------------
    # Edge case 7: Invalid numeric scores (NaN, Inf) handled safely
    # ------------------------------------------------------------------
    def test_invalid_numeric_scores(self) -> None:
        calc = ConfidenceCalculator()
        res = calc.calculate(
            {
                "retrieval": float("nan"),
                "reranking": float("inf"),
                "citation": -5.0,
                "answerability": 10.0,
            }
        )
        assert 0.0 <= res.confidence <= 1.0
        assert res.signals.retrieval == 0.0
        assert res.signals.reranking == 0.0  # Non-finite values safely clamp to 0.0
        assert res.signals.citation_support == 0.0  # Negative score clamped to 0.0
        assert res.signals.answerability == 1.0  # Score > 1.0 clamped to 1.0
