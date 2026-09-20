"""
Verification data models for the Citation Verification Layer.

Defines:
- VerificationStatus: SUPPORTED / UNSUPPORTED / UNCERTAIN / UNCITED / INVALID_CITATION
- VerificationMode: rule_based / llm / hybrid
- VerificationPolicy: configuration controlling verification behaviour.
- Claim: a factual statement extracted from an answer with associated citation IDs.
- ClaimVerificationResult: outcome for one claim.
- VerificationResult: overall outcome for all claims in an answer.

Semantics of VerificationStatus
--------------------------------
SUPPORTED        The cited evidence sufficiently supports the claim.
UNSUPPORTED      The cited evidence contradicts or fails to support the claim,
                 OR the citation ID does not exist in the registry.
UNCERTAIN        Evidence is ambiguous, incomplete, conflicting, or partially
                 supporting; the verifier cannot determine support confidently.
UNCITED          The claim appears factual but has no citation reference.
                 This is distinct from UNSUPPORTED — the issue is a missing
                 evidence reference, not a contradiction.
INVALID_CITATION A citation ID referenced by the claim does not exist in
                 the authoritative registry; evidence cannot be resolved.

Confidence
----------
If a semantic verifier produces a confidence score, it is preserved in
ClaimVerificationResult.confidence. This score reflects the semantic
verifier's internal estimate and should NOT be treated as a calibrated
probability unless the system has been formally calibrated.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(str, Enum):
    """
    Structured status of a citation verification outcome.

    SUPPORTED        — Evidence clearly supports the claim.
    UNSUPPORTED      — Evidence contradicts, is irrelevant, or does not support.
    UNCERTAIN        — Evidence is ambiguous, partial, or conflicting.
    UNCITED          — Claim has no citation; evidence reference is missing.
    INVALID_CITATION — Citation ID not found in the authoritative registry.
    """

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNCERTAIN = "UNCERTAIN"
    UNCITED = "UNCITED"
    INVALID_CITATION = "INVALID_CITATION"


class VerificationMode(str, Enum):
    """
    Verification execution strategy.

    RULE_BASED  — Deterministic checks only (fast, no LLM call).
    LLM         — Semantic LLM-based verification only.
    HYBRID      — Rule-based first; escalate to LLM for UNCERTAIN cases.
    """

    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"


class VerificationPolicy(BaseModel):
    """
    Configuration controlling how citation verification is performed.

    Attributes:
        enabled: Master switch; if False, verification is skipped entirely.
        mode: Execution strategy (rule_based, llm, hybrid).
        fail_on_unsupported: If True, raise an error when any claim is UNSUPPORTED.
    """

    enabled: bool = Field(
        default=True,
        description="Whether citation verification is active.",
    )
    mode: VerificationMode = Field(
        default=VerificationMode.RULE_BASED,
        description="Verification strategy: rule_based, llm, or hybrid.",
    )
    fail_on_unsupported: bool = Field(
        default=False,
        description="Raise VerificationError when any claim is UNSUPPORTED.",
    )

    model_config = ConfigDict(frozen=True)


class Claim(BaseModel):
    """
    A single factual statement extracted from a generated answer.

    A claim may reference zero or more citation IDs. Statements with no
    citation IDs receive status UNCITED. Claims referencing citation IDs
    that do not exist in the registry receive status INVALID_CITATION.

    Attributes:
        claim_id: Sequential 1-based integer identifier within the answer.
        text: The factual statement text (citation markers stripped).
        citation_ids: 1-based citation IDs referenced by this statement.
    """

    claim_id: int = Field(
        ...,
        ge=1,
        description="1-based sequential claim identifier within the answer.",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Factual statement text with citation markers removed.",
    )
    citation_ids: list[int] = Field(
        default_factory=list,
        description="1-based citation IDs referenced by this claim.",
    )

    model_config = ConfigDict(frozen=True)


class ClaimVerificationResult(BaseModel):
    """
    Verification outcome for a single extracted claim.

    Attributes:
        claim_id: Identifier matching the originating Claim.
        claim: Original claim text (citation markers stripped).
        citation_ids: Citation IDs referenced by the claim.
        status: Verification outcome for this claim.
        reason: Human-readable explanation of the outcome.
        evidence_snippets: Resolved evidence texts used for verification.
        confidence: Optional confidence score from semantic verifier (0–1).
                    Not a calibrated probability unless formally validated.
        rule_check_latency_ms: Latency of the rule-based check stage.
        semantic_latency_ms: Latency of semantic verification (if performed).
    """

    claim_id: int = Field(
        ...,
        ge=1,
        description="1-based claim identifier.",
    )
    claim: str = Field(
        ...,
        description="Factual statement text being verified.",
    )
    citation_ids: list[int] = Field(
        default_factory=list,
        description="Citation IDs referenced by this claim.",
    )
    status: VerificationStatus = Field(
        ...,
        description="Verification outcome status.",
    )
    reason: str = Field(
        default="",
        description="Explanation of the verification decision.",
    )
    evidence_snippets: list[str] = Field(
        default_factory=list,
        description="Evidence texts resolved from the citation registry.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Semantic verifier confidence (0–1). Not a calibrated probability.",
    )
    rule_check_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Monotonic latency of rule-based checks in milliseconds.",
    )
    semantic_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Monotonic latency of semantic verification in milliseconds.",
    )

    model_config = ConfigDict(frozen=True)

    @property
    def total_latency_ms(self) -> float:
        """Total latency for this claim's verification."""
        return self.rule_check_latency_ms + self.semantic_latency_ms


class VerificationResult(BaseModel):
    """
    Aggregated verification outcome for all claims in a generated answer.

    Attributes:
        overall_status: Aggregate status across all claims.
                        SUPPORTED if all supported; UNSUPPORTED if any unsupported;
                        UNCERTAIN if any uncertain (and no unsupported);
                        UNCITED if any uncited (and no stronger failure).
        claims: Individual claim-level verification results.
        answer: The original generated answer text.
        total_claims: Total number of claims extracted.
        supported_count: Claims verified as SUPPORTED.
        unsupported_count: Claims verified as UNSUPPORTED.
        uncertain_count: Claims verified as UNCERTAIN.
        uncited_count: Claims with no citation reference (UNCITED).
        invalid_citation_count: Claims with citation IDs absent from registry.
        total_verification_latency_ms: Wall-clock time for full verification.
    """

    overall_status: VerificationStatus = Field(
        ...,
        description="Aggregate verification status across all claims.",
    )
    claims: list[ClaimVerificationResult] = Field(
        default_factory=list,
        description="Per-claim verification results.",
    )
    answer: str = Field(
        default="",
        description="The original generated answer text.",
    )
    total_claims: int = Field(
        default=0,
        ge=0,
        description="Number of claims extracted from the answer.",
    )
    supported_count: int = Field(default=0, ge=0)
    unsupported_count: int = Field(default=0, ge=0)
    uncertain_count: int = Field(default=0, ge=0)
    uncited_count: int = Field(default=0, ge=0)
    invalid_citation_count: int = Field(default=0, ge=0)
    total_verification_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total wall-clock latency for the full verification pass (ms).",
    )

    model_config = ConfigDict(frozen=True)

    @classmethod
    def aggregate(
        cls,
        answer: str,
        claim_results: list[ClaimVerificationResult],
        total_latency_ms: float = 0.0,
    ) -> "VerificationResult":
        """
        Build a VerificationResult from a list of per-claim results.

        Aggregation priority (highest severity wins):
          UNSUPPORTED > UNCERTAIN > UNCITED > INVALID_CITATION > SUPPORTED

        If there are no claims at all, overall_status is SUPPORTED.
        """
        counts: dict[VerificationStatus, int] = {s: 0 for s in VerificationStatus}
        for r in claim_results:
            counts[r.status] += 1

        # Derive aggregate status: most severe failure dominates
        if counts[VerificationStatus.UNSUPPORTED] > 0:
            overall = VerificationStatus.UNSUPPORTED
        elif counts[VerificationStatus.UNCERTAIN] > 0:
            overall = VerificationStatus.UNCERTAIN
        elif counts[VerificationStatus.INVALID_CITATION] > 0:
            overall = VerificationStatus.INVALID_CITATION
        elif counts[VerificationStatus.UNCITED] > 0:
            overall = VerificationStatus.UNCITED
        else:
            overall = VerificationStatus.SUPPORTED

        return cls(
            overall_status=overall,
            claims=claim_results,
            answer=answer,
            total_claims=len(claim_results),
            supported_count=counts[VerificationStatus.SUPPORTED],
            unsupported_count=counts[VerificationStatus.UNSUPPORTED],
            uncertain_count=counts[VerificationStatus.UNCERTAIN],
            uncited_count=counts[VerificationStatus.UNCITED],
            invalid_citation_count=counts[VerificationStatus.INVALID_CITATION],
            total_verification_latency_ms=total_latency_ms,
        )
