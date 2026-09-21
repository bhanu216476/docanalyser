"""
Answerability Evaluator for RAG Confidence Scoring.

Assesses whether the available retrieved evidence and generated response
are sufficient to answer the user's query.

Uses existing pipeline evidence and verification signals deterministically
without requiring extra LLM calls or an independent hallucination detector.

Status Mapping:
- ANSWERABLE          → 1.0
- PARTIALLY_ANSWERABLE → 0.5
- NOT_ANSWERABLE      → 0.0
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Sequence, Union

from app.confidence.models import AnswerabilityStatus
from app.context.models import BuiltContext
from app.reranking.models import RerankedResult
from app.retrieval.models import RetrievalResult
from app.verification.models import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)

# Standard RAG refusal and missing-information indicators
REFUSAL_PATTERNS = [
    r"\bi (?:do not|don'?t) have enough information\b",
    r"\b(?:not|insufficient)\s+(?:information|context|evidence)\s+(?:provided|found|available)\b",
    r"\bthe provided (?:context|documents?|text) does not contain\b",
    r"\b(?:cannot|can not|unable to) answer(?: this)?(?: question)?\b",
    r"\b(?:not mentioned|not specified|not stated) in the (?:provided|given) (?:context|document)\b",
    r"\bno relevant information found\b",
]

_COMPILED_REFUSAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in REFUSAL_PATTERNS]


class AnswerabilityEvaluator:
    """
    Deterministic answerability evaluator.
    """

    STATUS_SCORES: dict[AnswerabilityStatus, float] = {
        AnswerabilityStatus.ANSWERABLE: 1.0,
        AnswerabilityStatus.PARTIALLY_ANSWERABLE: 0.5,
        AnswerabilityStatus.NOT_ANSWERABLE: 0.0,
    }

    @classmethod
    def is_refusal(cls, answer: str) -> bool:
        """Check if generated text expresses a standard unanswerable refusal."""
        if not answer or not answer.strip():
            return True
        text = answer.strip()
        return any(pattern.search(text) for pattern in _COMPILED_REFUSAL_PATTERNS)

    @classmethod
    def evaluate(
        cls,
        query: str,
        answer: str,
        evidence_chunks: Sequence[Union[RetrievalResult, RerankedResult]],
        verification_result: Optional[VerificationResult] = None,
    ) -> tuple[AnswerabilityStatus, float, str]:
        """
        Evaluate answerability status and score.

        Returns:
            Tuple of (AnswerabilityStatus, score_in_0_to_1, reason_string).
        """
        # 1. Empty query or answer
        if not query or not query.strip():
            return (
                AnswerabilityStatus.NOT_ANSWERABLE,
                0.0,
                "Query string is empty or whitespace.",
            )

        if not answer or not answer.strip():
            return (
                AnswerabilityStatus.NOT_ANSWERABLE,
                0.0,
                "Generated answer is empty.",
            )

        # 2. No evidence chunks available
        if not evidence_chunks:
            return (
                AnswerabilityStatus.NOT_ANSWERABLE,
                0.0,
                "No evidence chunks were retrieved or provided in context.",
            )

        # 3. Model explicitly refused or indicated missing information
        if cls.is_refusal(answer):
            return (
                AnswerabilityStatus.NOT_ANSWERABLE,
                0.0,
                "Generated answer expresses explicit lack of evidence / refusal to answer.",
            )

        # 4. Use verification result if available
        if verification_result is not None:
            if verification_result.total_claims == 0:
                # No claims were extracted (e.g. general sentence or conversational)
                return (
                    AnswerabilityStatus.PARTIALLY_ANSWERABLE,
                    0.5,
                    "No verifiable factual claims extracted from answer.",
                )

            # Check for total unsupport
            all_unsupported_or_invalid = all(
                c.status in (VerificationStatus.UNSUPPORTED, VerificationStatus.INVALID_CITATION)
                for c in verification_result.claims
            )
            if all_unsupported_or_invalid:
                return (
                    AnswerabilityStatus.NOT_ANSWERABLE,
                    0.0,
                    "All extracted claims are unsupported or reference invalid citations.",
                )

            # Check if all claims are supported
            all_supported = all(
                c.status == VerificationStatus.SUPPORTED
                for c in verification_result.claims
            )
            if all_supported:
                return (
                    AnswerabilityStatus.ANSWERABLE,
                    1.0,
                    "All extracted claims are fully supported by cited evidence.",
                )

            # Partial support or uncertainty
            return (
                AnswerabilityStatus.PARTIALLY_ANSWERABLE,
                0.5,
                f"Partial answerability: {verification_result.supported_count}/{verification_result.total_claims} claims supported.",
            )

        # 5. Fallback when verification is omitted but evidence & answer exist
        return (
            AnswerabilityStatus.ANSWERABLE,
            1.0,
            "Evidence retrieved and answer generated without refusal indicators.",
        )
