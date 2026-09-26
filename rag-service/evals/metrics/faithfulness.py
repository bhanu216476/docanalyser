"""
Faithfulness metric module.

Leverages the existing Citation Verification Layer (CitationVerifier)
to compute dataset-level and query-level faithfulness metrics.
"""

from __future__ import annotations

from typing import Any, Optional
from app.verification.models import VerificationResult, VerificationStatus


def evaluate_faithfulness(
    verification_result: Optional[VerificationResult],
    answerable: bool = True,
) -> float:
    """
    Measure whether the generated answer is supported by the retrieved/context evidence.

    Reuses the existing Citation Verification infrastructure:
    - If verification result has claims: returns (supported_claims / total_claims).
    - If overall_status is SUPPORTED: returns 1.0.
    - If no claims extracted and question is unanswerable (refusal/abstention): returns 1.0.
    - If answer is ungrounded / unsupported: returns 0.0.

    Args:
        verification_result: The VerificationResult produced by the pipeline.
        answerable: Whether the question is answerable.

    Returns:
        Faithfulness score in [0.0, 1.0].
    """
    if verification_result is None:
        return 0.0

    if verification_result.total_claims == 0:
        # No factual claims extracted (e.g. clean refusal)
        return 1.0 if not answerable or verification_result.overall_status == VerificationStatus.SUPPORTED else 0.5

    # Proportion of verified supported claims
    supported = float(verification_result.supported_count)
    total = float(verification_result.total_claims)

    score = supported / total if total > 0 else 0.0
    return round(score, 4)
