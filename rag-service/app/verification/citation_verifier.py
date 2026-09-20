"""
CitationVerifier — the central service of the Citation Verification Layer.

Responsibility
--------------
Verify whether claims made in a generated answer are actually supported
by the evidence chunks referenced by their citations.

The verifier answers:
    Does the cited evidence support the claim made in the generated answer?

It does NOT answer:
    Is the claim generally true in the real world?

Verification is against the supplied RAG evidence only.

Pipeline
--------
    Generated Answer
          ↓
    Extract Claims (ClaimExtractor)
          ↓
    Extract Citation IDs
          ↓
    Validate Citation IDs (check against registry)
          ↓
    Resolve Evidence (chunk content from registry)
          ↓
    Rule-Based Checks (RuleBasedVerifier)
          ↓
    Semantic Verification if needed (EvidenceVerifier)
          ↓
    VerificationResult

Modes (VerificationMode)
------------------------
RULE_BASED : Only deterministic checks. No LLM call.
LLM        : Only semantic LLM verification. Skips rule pre-checks.
HYBRID     : Rule-based first; escalates to LLM for inconclusive cases.

Multi-citation aggregation
--------------------------
When a claim cites multiple sources:
    - Evidence texts are combined for rule and semantic checks.
    - If sources conflict (different specific numbers), status = UNCERTAIN.
    - SUPPORTED only if all evidence collectively supports the claim.
    - One supporting citation is NOT sufficient when another contradicts.

Batch efficiency
----------------
All claims in an answer are processed in a single pass. The semantic
verifier is only called for claims where rule checks are inconclusive,
minimising unnecessary LLM calls.

Security
--------
Answer and evidence text are treated as untrusted. The verification
prompt enforces explicit delimiters so that claim/evidence text cannot
override verification instructions. The CitationVerifier never trusts
document-provided instructions.
"""

from __future__ import annotations

import logging
import time
from typing import Mapping, Optional, Union

from app.context.models import Citation
from app.verification.models import (
    Claim,
    ClaimVerificationResult,
    VerificationMode,
    VerificationPolicy,
    VerificationResult,
    VerificationStatus,
)
from app.verification.claim_extractor import ClaimExtractor
from app.verification.rules import RuleBasedVerifier
from app.verification.evidence_verifier import (
    EvidenceVerifier,
    MockEvidenceVerifier,
    SemanticVerificationOutcome,
)

logger = logging.getLogger(__name__)

# Registry type alias — matches BuiltContext.citation_registry
CitationRegistry = Mapping[Union[int, str], Citation]


def _normalize_registry(registry: CitationRegistry) -> dict[int, Citation]:
    """
    Normalise a citation registry to integer keys.

    Supports both int keys and string keys like '[1]', '1'.
    """
    result: dict[int, Citation] = {}
    for k, v in registry.items():
        if isinstance(k, int):
            result[k] = v
        elif isinstance(k, str):
            import re
            m = re.search(r"\d+", k)
            if m:
                result[int(m.group(0))] = v
    return result


class CitationVerifier:
    """
    Central citation verification service.

    Args:
        policy: VerificationPolicy controlling mode and behaviour.
        claim_extractor: ClaimExtractor instance. Defaults to ClaimExtractor().
        rule_verifier: RuleBasedVerifier instance. Defaults to RuleBasedVerifier().
        semantic_verifier: EvidenceVerifier implementation.
                           Defaults to MockEvidenceVerifier() for safe offline use.
                           Supply an LLMEvidenceVerifier for production LLM mode.
    """

    def __init__(
        self,
        policy: Optional[VerificationPolicy] = None,
        claim_extractor: Optional[ClaimExtractor] = None,
        rule_verifier: Optional[RuleBasedVerifier] = None,
        semantic_verifier: Optional[EvidenceVerifier] = None,
    ) -> None:
        self._policy = policy or VerificationPolicy()
        self._extractor = claim_extractor or ClaimExtractor()
        self._rules = rule_verifier or RuleBasedVerifier()
        self._semantic = semantic_verifier or MockEvidenceVerifier()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(
        self,
        answer: str,
        citation_registry: CitationRegistry,
    ) -> VerificationResult:
        """
        Verify all claims in a generated answer against the citation registry.

        Args:
            answer: Raw generated answer text (may contain [N] citation markers).
            citation_registry: Authoritative registry from Context Builder /
                               BuiltContext.citation_registry. Provides the
                               ground-truth chunk content for evidence resolution.
                               Never re-retrieves from Qdrant.

        Returns:
            VerificationResult with per-claim and aggregate outcomes.
        """
        t_start = time.monotonic()

        if not self._policy.enabled:
            logger.debug("Verification disabled by policy; returning SUPPORTED.")
            return VerificationResult.aggregate(
                answer=answer,
                claim_results=[],
                total_latency_ms=0.0,
            )

        # Normalise registry to int keys
        registry = _normalize_registry(citation_registry)
        registry_ids: set[int] = set(registry.keys())

        # Step 1: Extract claims
        claims = self._extractor.extract(answer)

        if not claims:
            logger.debug("No claims extracted from answer; returning SUPPORTED.")
            return VerificationResult.aggregate(
                answer=answer,
                claim_results=[],
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Step 2: Verify each claim
        claim_results: list[ClaimVerificationResult] = []
        for claim in claims:
            result = self._verify_claim(claim, registry, registry_ids)
            claim_results.append(result)

        total_latency_ms = (time.monotonic() - t_start) * 1000.0

        verification_result = VerificationResult.aggregate(
            answer=answer,
            claim_results=claim_results,
            total_latency_ms=total_latency_ms,
        )

        logger.info(
            "Verification complete: %d claims, overall=%s, latency=%.1fms",
            len(claims),
            verification_result.overall_status.value,
            total_latency_ms,
        )

        return verification_result

    # ------------------------------------------------------------------
    # Internal per-claim verification
    # ------------------------------------------------------------------

    def _verify_claim(
        self,
        claim: Claim,
        registry: dict[int, Citation],
        registry_ids: set[int],
    ) -> ClaimVerificationResult:
        """
        Verify a single claim against available registry evidence.
        """
        # Case 1: UNCITED — no citation references at all
        if not claim.citation_ids:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim=claim.text,
                citation_ids=[],
                status=VerificationStatus.UNCITED,
                reason=(
                    "The claim contains no citation reference. "
                    "Verification is not possible without an evidence source."
                ),
            )

        # Case 2: Single citation
        if len(claim.citation_ids) == 1:
            return self._verify_single_citation(claim, registry, registry_ids)

        # Case 3: Multiple citations
        return self._verify_multi_citation(claim, registry, registry_ids)

    def _verify_single_citation(
        self,
        claim: Claim,
        registry: dict[int, Citation],
        registry_ids: set[int],
    ) -> ClaimVerificationResult:
        """Verify a claim that references exactly one citation."""
        cid = claim.citation_ids[0]
        registry_has_id = cid in registry_ids

        # Resolve evidence text
        evidence_text = ""
        if registry_has_id:
            citation_obj = registry[cid]
            evidence_text = self._resolve_evidence_text(citation_obj)

        # Rule-based check
        rule_outcome = self._rules.check(
            claim=claim.text,
            evidence=evidence_text,
            citation_id=cid,
            registry_has_id=registry_has_id,
        )

        # If rule produced a decisive result
        if rule_outcome.status is not None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim=claim.text,
                citation_ids=claim.citation_ids,
                status=rule_outcome.status,
                reason=rule_outcome.reason,
                evidence_snippets=[evidence_text] if evidence_text else [],
                rule_check_latency_ms=rule_outcome.latency_ms,
            )

        # Escalate to semantic verifier if mode permits
        if self._policy.mode == VerificationMode.RULE_BASED:
            # Rule-based only: inconclusive = UNCERTAIN
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim=claim.text,
                citation_ids=claim.citation_ids,
                status=VerificationStatus.UNCERTAIN,
                reason=(
                    "Rule-based verification was inconclusive. "
                    "Semantic verification is disabled in rule_based mode."
                ),
                evidence_snippets=[evidence_text] if evidence_text else [],
                rule_check_latency_ms=rule_outcome.latency_ms,
            )

        # Semantic verification
        sem_outcome = self._semantic.verify(claim.text, evidence_text)

        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim=claim.text,
            citation_ids=claim.citation_ids,
            status=sem_outcome.status,
            reason=sem_outcome.reason,
            evidence_snippets=[evidence_text] if evidence_text else [],
            confidence=sem_outcome.confidence,
            rule_check_latency_ms=rule_outcome.latency_ms,
            semantic_latency_ms=sem_outcome.latency_ms,
        )

    def _verify_multi_citation(
        self,
        claim: Claim,
        registry: dict[int, Citation],
        registry_ids: set[int],
    ) -> ClaimVerificationResult:
        """
        Verify a claim that references multiple citations.

        Aggregation behaviour:
        - If any citation ID is absent from registry → INVALID_CITATION.
        - If evidence sources conflict (numeric contradiction) → UNCERTAIN.
        - SUPPORTED only when all evidence collectively supports the claim.
        - If any source contradicts → UNSUPPORTED.
        """
        # Collect evidence items; detect missing IDs
        evidence_items: list[tuple[int, str]] = []
        for cid in claim.citation_ids:
            if cid not in registry_ids:
                return ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim=claim.text,
                    citation_ids=claim.citation_ids,
                    status=VerificationStatus.INVALID_CITATION,
                    reason=f"Citation [{cid}] does not exist in the registry.",
                )
            ev_text = self._resolve_evidence_text(registry[cid])
            evidence_items.append((cid, ev_text))

        evidence_texts = [ev for _, ev in evidence_items]

        # Rule-based multi-evidence check
        rule_outcome = self._rules.check_multi_evidence(
            claim=claim.text,
            evidence_items=evidence_items,
            registry_ids=registry_ids,
        )

        if rule_outcome.status is not None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim=claim.text,
                citation_ids=claim.citation_ids,
                status=rule_outcome.status,
                reason=rule_outcome.reason,
                evidence_snippets=evidence_texts,
                rule_check_latency_ms=rule_outcome.latency_ms,
            )

        # Escalate to semantic if permitted
        if self._policy.mode == VerificationMode.RULE_BASED:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim=claim.text,
                citation_ids=claim.citation_ids,
                status=VerificationStatus.UNCERTAIN,
                reason=(
                    "Rule-based multi-citation verification was inconclusive. "
                    "Semantic verification is disabled in rule_based mode."
                ),
                evidence_snippets=evidence_texts,
                rule_check_latency_ms=rule_outcome.latency_ms,
            )

        sem_outcome = self._semantic.verify_multi(claim.text, evidence_texts)

        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim=claim.text,
            citation_ids=claim.citation_ids,
            status=sem_outcome.status,
            reason=sem_outcome.reason,
            evidence_snippets=evidence_texts,
            confidence=sem_outcome.confidence,
            rule_check_latency_ms=rule_outcome.latency_ms,
            semantic_latency_ms=sem_outcome.latency_ms,
        )

    # ------------------------------------------------------------------
    # Evidence resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_evidence_text(citation: Citation) -> str:
        """
        Resolve the authoritative evidence text from a Citation object.

        The citation registry stores the chunk content in the metadata dict
        under the key 'content', or directly as a field if available.
        We do NOT retrieve from Qdrant; we use what the Context Builder stored.

        Resolution order:
        1. citation.metadata.get('content') — chunk content stored by ContextBuilder
        2. citation.metadata.get('text')    — alternative content key
        3. ''                               — no content available
        """
        meta = dict(citation.metadata) if citation.metadata else {}
        content = meta.get("content") or meta.get("text") or ""
        return str(content).strip()
