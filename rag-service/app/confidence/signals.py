"""
Signal Extractor for RAG Confidence Scoring.

Aggregates and normalizes evidence from pipeline stages into structured ConfidenceSignals:
1. Retrieval Signal (Dense, BM25, RRF) via ScoreNormalizer
2. Reranking Signal (Candidate Reranker) via ScoreNormalizer
3. Citation Support Signal (Citation Verification)
4. Answerability Signal (AnswerabilityEvaluator)
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence, Union

from app.confidence.answerability import AnswerabilityEvaluator
from app.confidence.models import AnswerabilityStatus, ConfidenceSignals
from app.confidence.normalizer import ScoreNormalizer
from app.reranking.models import RerankedResult
from app.retrieval.models import HybridRetrievalResult, RetrievalResult
from app.verification.models import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)

# Deterministic citation verification status mapping
CITATION_STATUS_SIGNAL_MAP: dict[VerificationStatus, float] = {
    VerificationStatus.SUPPORTED: 1.0,
    VerificationStatus.UNCERTAIN: 0.5,
    VerificationStatus.UNSUPPORTED: 0.0,
    VerificationStatus.UNCITED: 0.0,
    VerificationStatus.INVALID_CITATION: 0.0,
}


def calculate_citation_support_signal(
    verification_result: Optional[VerificationResult],
    answer: str = "",
) -> float:
    """
    Calculate normalized citation support signal from verification results.

    Mapping:
        SUPPORTED        → 1.0
        UNCERTAIN        → 0.5
        UNSUPPORTED      → 0.0
        UNCITED          → 0.0
        INVALID_CITATION → 0.0

    For multiple claims, averages the deterministic status values across all claims.
    If no verification result exists or answer is empty, returns 0.0.
    """
    if not answer or not answer.strip():
        return 0.0

    if verification_result is None:
        return 0.0

    if not verification_result.claims:
        # If verification had no claims extracted:
        # If the answer made factual assertions without citations, it would be UNCITED.
        # If answer is completely devoid of claims/citations, support is 0.0.
        return 0.0

    claim_signals = [
        CITATION_STATUS_SIGNAL_MAP.get(claim.status, 0.0)
        for claim in verification_result.claims
    ]

    support_score = sum(claim_signals) / len(claim_signals)
    return ScoreNormalizer.clamp(support_score, 0.0, 1.0)


class SignalExtractor:
    """
    Extracts and standardizes normalized confidence signals from RAG execution stages.
    """

    @classmethod
    def extract_signals(
        cls,
        query: str,
        answer: str,
        retrieval_candidates: Sequence[Union[RetrievalResult, HybridRetrievalResult, RerankedResult]],
        reranked_candidates: Sequence[RerankedResult],
        verification_result: Optional[VerificationResult] = None,
        rrf_k: int = 60,
        num_sources: int = 2,
    ) -> ConfidenceSignals:
        """
        Extract all 4 primary confidence signals from pipeline artifacts.
        """
        # 1. Retrieval Signal
        retrieval_signal = ScoreNormalizer.aggregate_retrieval_signal(
            candidates=retrieval_candidates,
            k=rrf_k,
            num_sources=num_sources,
            strategy="top1",
        )

        # 2. Reranking Signal
        reranking_signal = ScoreNormalizer.aggregate_reranking_signal(
            candidates=reranked_candidates,
            is_logit=False,
            strategy="top1",
        )

        # 3. Citation Support Signal
        citation_support_signal = calculate_citation_support_signal(
            verification_result=verification_result,
            answer=answer,
        )

        # 4. Answerability Signal
        evidence = reranked_candidates if reranked_candidates else retrieval_candidates
        _, answerability_signal, _ = AnswerabilityEvaluator.evaluate(
            query=query,
            answer=answer,
            evidence_chunks=evidence,
            verification_result=verification_result,
        )

        return ConfidenceSignals(
            retrieval=retrieval_signal,
            reranking=reranking_signal,
            citation_support=citation_support_signal,
            answerability=answerability_signal,
        )
