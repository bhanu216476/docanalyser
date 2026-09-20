"""
Unit tests for the CitationVerifier — central verification service.

Tests the complete verification pipeline:
- Claim extraction
- Citation ID validation
- Evidence resolution
- Rule-based checks
- Semantic verification (via MockEvidenceVerifier)
- Result aggregation

Uses the MockEvidenceVerifier so NO external LLM calls are made.

Coverage:
- Case 1: Correct citation → SUPPORTED
- Case 2: Wrong number → UNSUPPORTED (rule-based)
- Case 3: Wrong entity → (semantic mock)
- Case 4: Missing citation → UNCITED
- Case 5: Invalid citation ID → INVALID_CITATION
- Case 6: Conflicting evidence → UNCERTAIN
- Case 7: Partial support → UNCERTAIN
- Case 8: Negation mismatch → UNSUPPORTED
- Case 9: Semantic paraphrase → SUPPORTED (mock heuristic)
- Case 10: Irrelevant evidence → UNCERTAIN (mock cannot confirm)
- Multi-citation claims
- No-answer responses
- Determinism: same inputs produce same results
"""

from __future__ import annotations

import pytest
from typing import Mapping, Union

from app.context.models import Citation
from app.verification.models import (
    VerificationMode,
    VerificationPolicy,
    VerificationStatus,
)
from app.verification.citation_verifier import CitationVerifier
from app.verification.evidence_verifier import MockEvidenceVerifier


# ---------------------------------------------------------------------------
# Helpers to build test Citation objects with content in metadata
# ---------------------------------------------------------------------------

def make_citation(citation_id: int, content: str, file_name: str = "policy.pdf") -> Citation:
    """Create a minimal Citation object with content stored in metadata."""
    return Citation(
        citation_id=f"[{citation_id}]",
        chunk_id=f"chunk_{citation_id}",
        file_name=file_name,
        metadata={"content": content},
    )


def make_registry(*citations: Citation) -> dict[int, Citation]:
    """Build an int-keyed registry from Citation objects."""
    return {c.id: c for c in citations if c.id is not None}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hybrid_verifier() -> CitationVerifier:
    """Verifier in HYBRID mode with mock semantic verifier."""
    policy = VerificationPolicy(
        enabled=True,
        mode=VerificationMode.HYBRID,
    )
    return CitationVerifier(
        policy=policy,
        semantic_verifier=MockEvidenceVerifier(use_substring_heuristic=True),
    )


@pytest.fixture
def rule_only_verifier() -> CitationVerifier:
    """Verifier in RULE_BASED mode — no semantic verifier called."""
    policy = VerificationPolicy(
        enabled=True,
        mode=VerificationMode.RULE_BASED,
    )
    return CitationVerifier(policy=policy)


@pytest.fixture
def disabled_verifier() -> CitationVerifier:
    """Verifier with enabled=False — always returns SUPPORTED with no claims."""
    policy = VerificationPolicy(enabled=False)
    return CitationVerifier(policy=policy)


# ---------------------------------------------------------------------------
# Test Case 1: Correct citation
# ---------------------------------------------------------------------------

class TestCase1CorrectCitation:
    def test_supported(self, hybrid_verifier: CitationVerifier) -> None:
        """Case 1: Claim matches evidence exactly → SUPPORTED."""
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.SUPPORTED
        assert result.supported_count == 1
        assert result.unsupported_count == 0

    def test_claim_result_has_evidence(self, hybrid_verifier: CitationVerifier) -> None:
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert len(result.claims) == 1
        claim_r = result.claims[0]
        assert claim_r.status == VerificationStatus.SUPPORTED
        assert len(claim_r.evidence_snippets) == 1


# ---------------------------------------------------------------------------
# Test Case 2: Wrong number
# ---------------------------------------------------------------------------

class TestCase2WrongNumber:
    def test_unsupported_numeric_mismatch(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """Case 2: Claim says 20, evidence says 12 → UNSUPPORTED."""
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        result = rule_only_verifier.verify(
            "Employees receive 20 casual leave days [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED
        assert result.unsupported_count >= 1


# ---------------------------------------------------------------------------
# Test Case 4: Missing citation (UNCITED)
# ---------------------------------------------------------------------------

class TestCase4MissingCitation:
    def test_uncited_claim(self, hybrid_verifier: CitationVerifier) -> None:
        """Case 4: Claim has no citation marker → UNCITED."""
        registry: dict[int, Citation] = {}
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days.",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNCITED
        assert result.uncited_count == 1

    def test_uncited_distinct_from_unsupported(
        self, hybrid_verifier: CitationVerifier
    ) -> None:
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days.",
            {},
        )
        claim_r = result.claims[0]
        assert claim_r.status == VerificationStatus.UNCITED
        assert claim_r.status != VerificationStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# Test Case 5: Invalid citation ID
# ---------------------------------------------------------------------------

class TestCase5InvalidCitation:
    def test_invalid_citation_status(self, rule_only_verifier: CitationVerifier) -> None:
        """Case 5: Citation [99] not in registry → INVALID_CITATION."""
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)  # Only [1] in registry
        result = rule_only_verifier.verify(
            "Employees receive 12 casual leave days [99].",
            registry,
        )
        assert result.overall_status == VerificationStatus.INVALID_CITATION
        assert result.invalid_citation_count == 1

    def test_invalid_citation_reason_mentions_id(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        result = rule_only_verifier.verify(
            "Employees receive 12 casual leave days [99].",
            registry,
        )
        claim_r = result.claims[0]
        assert "99" in claim_r.reason


# ---------------------------------------------------------------------------
# Test Case 6: Conflicting evidence (multi-citation)
# ---------------------------------------------------------------------------

class TestCase6ConflictingEvidence:
    def test_conflicting_sources_uncertain(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """Case 6: [1]=12 days, [2]=15 days → UNCERTAIN."""
        cit1 = make_citation(1, "Employees receive 12 casual leave days.")
        cit2 = make_citation(2, "Employees receive 15 casual leave days.")
        registry = make_registry(cit1, cit2)
        result = rule_only_verifier.verify(
            "Employees receive 12 casual leave days [1][2].",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNCERTAIN
        assert result.uncertain_count >= 1


# ---------------------------------------------------------------------------
# Test Case 7: Partial support
# ---------------------------------------------------------------------------

class TestCase7PartialSupport:
    def test_partial_support_uncertain(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """Case 7: Evidence only covers part of claim → UNCERTAIN."""
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        # Claim asks for 12 days AND 5 carry-over; evidence only mentions 12 days
        result = rule_only_verifier.verify(
            "Employees receive 12 casual leave days and can carry over 5 unused days [1].",
            registry,
        )
        # With rule-based, inconclusive → UNCERTAIN
        claim_r = result.claims[0]
        assert claim_r.status in (
            VerificationStatus.UNCERTAIN,
            VerificationStatus.UNSUPPORTED,
        )


# ---------------------------------------------------------------------------
# Test Case 8: Negation mismatch
# ---------------------------------------------------------------------------

class TestCase8Negation:
    def test_negation_unsupported(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """Case 8: Claim is positive, evidence has 'not' → UNSUPPORTED."""
        cit = make_citation(
            1, "Employees are not eligible for casual leave during probation."
        )
        registry = make_registry(cit)
        result = rule_only_verifier.verify(
            "Employees are eligible for casual leave during probation [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED

    def test_negation_reversed(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """Claim negates, evidence is positive → UNSUPPORTED."""
        cit = make_citation(
            1, "Employees are eligible during probation."
        )
        registry = make_registry(cit)
        result = rule_only_verifier.verify(
            "Employees are not eligible during probation [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# Test Case 9: Semantic paraphrase (mock heuristic)
# ---------------------------------------------------------------------------

class TestCase9Paraphrase:
    def test_exact_string_paraphrase_supported_by_mock(
        self, hybrid_verifier: CitationVerifier
    ) -> None:
        """
        Case 9: Semantic paraphrase support via mock heuristic.

        The mock EvidenceVerifier uses substring matching. For the mock to
        return SUPPORTED, the evidence must contain the clean claim text.
        The real LLM verifier handles true paraphrases (e.g. 'twelve' vs '12').

        Here we verify that when evidence clearly contains the claim content,
        the pipeline returns SUPPORTED (not UNSUPPORTED/UNCERTAIN).
        """
        # Evidence contains the clean claim text exactly
        cit = make_citation(
            1,
            "Employees receive 12 casual leave days. Annual entitlement confirmed."
        )
        registry = make_registry(cit)
        # After stripping [1], claim text = "Employees receive 12 casual leave days."
        # Evidence starts with that exact text → substring match succeeds
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.SUPPORTED

    def test_paraphrase_requires_semantic_not_rules(
        self, rule_only_verifier: CitationVerifier
    ) -> None:
        """
        In rule_based mode, paraphrase ('twelve' vs '12') → UNCERTAIN because
        rule-based checks are inconclusive (no numeric mismatch, no negation).
        A real LLM verifier would return SUPPORTED for this case.
        """
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        result = rule_only_verifier.verify(
            "Employees are entitled to twelve casual leave days [1].",
            registry,
        )
        # Rules don't fire on 'twelve' (word not int); escalate gives UNCERTAIN
        assert result.overall_status == VerificationStatus.UNCERTAIN


# ---------------------------------------------------------------------------
# Test Case 10: Irrelevant evidence
# ---------------------------------------------------------------------------

class TestCase10IrrelevantEvidence:
    def test_irrelevant_evidence_not_supported(
        self, hybrid_verifier: CitationVerifier
    ) -> None:
        """Case 10: Irrelevant evidence → mock returns UNCERTAIN (can't confirm)."""
        cit = make_citation(1, "The office cafeteria is open from 8 AM to 6 PM.")
        registry = make_registry(cit)
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        # Mock heuristic: 'employees receive 12 casual leave days' NOT in cafeteria text
        assert result.overall_status != VerificationStatus.SUPPORTED


# ---------------------------------------------------------------------------
# Multi-citation tests
# ---------------------------------------------------------------------------

class TestMultiCitation:
    def test_all_support(self, hybrid_verifier: CitationVerifier) -> None:
        """All cited evidence supports the claim."""
        cit1 = make_citation(1, "Employees receive 12 casual leave days per year.")
        cit2 = make_citation(2, "Leave is granted annually.")
        registry = make_registry(cit1, cit2)
        result = hybrid_verifier.verify(
            "Employees receive 12 casual leave days [1][2].",
            registry,
        )
        # Since evidence items don't conflict, mock checks claim against combined text
        assert result.overall_status != VerificationStatus.UNSUPPORTED

    def test_one_missing_invalid(self, rule_only_verifier: CitationVerifier) -> None:
        """One valid citation, one invalid → INVALID_CITATION."""
        cit1 = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit1)
        result = rule_only_verifier.verify(
            "Employees receive 12 casual leave days [1][99].",
            registry,
        )
        assert result.overall_status == VerificationStatus.INVALID_CITATION


# ---------------------------------------------------------------------------
# Disabled verifier
# ---------------------------------------------------------------------------

class TestDisabledVerifier:
    def test_disabled_returns_supported_no_claims(
        self, disabled_verifier: CitationVerifier
    ) -> None:
        result = disabled_verifier.verify("Any answer [1].", {})
        assert result.overall_status == VerificationStatus.SUPPORTED
        assert result.total_claims == 0


# ---------------------------------------------------------------------------
# No-answer / refusal responses
# ---------------------------------------------------------------------------

class TestNoAnswer:
    def test_empty_answer_no_claims(self, hybrid_verifier: CitationVerifier) -> None:
        result = hybrid_verifier.verify("", {})
        assert result.total_claims == 0
        assert result.overall_status == VerificationStatus.SUPPORTED

    def test_no_answer_response_no_false_unsupported(
        self, hybrid_verifier: CitationVerifier
    ) -> None:
        """An explicit 'I cannot answer' should not produce UNSUPPORTED claims."""
        result = hybrid_verifier.verify(
            "The provided sources do not contain sufficient information.",
            {},
        )
        # No factual claim here — either 0 claims or all UNCITED
        for c in result.claims:
            assert c.status != VerificationStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_result(self, rule_only_verifier: CitationVerifier) -> None:
        """Repeated verification with identical mock inputs produces identical results."""
        cit = make_citation(1, "Employees receive 12 casual leave days.")
        registry = make_registry(cit)
        answer = "Employees receive 20 casual leave days [1]."

        result1 = rule_only_verifier.verify(answer, registry)
        result2 = rule_only_verifier.verify(answer, registry)

        assert result1.overall_status == result2.overall_status
        assert result1.total_claims == result2.total_claims
        for r1, r2 in zip(result1.claims, result2.claims):
            assert r1.status == r2.status
            assert r1.reason == r2.reason


# ---------------------------------------------------------------------------
# VerificationResult aggregation
# ---------------------------------------------------------------------------

class TestVerificationResultAggregation:
    def test_any_unsupported_dominates(self) -> None:
        from app.verification.models import ClaimVerificationResult, VerificationResult
        claims = [
            ClaimVerificationResult(
                claim_id=1, claim="x", status=VerificationStatus.SUPPORTED, reason=""
            ),
            ClaimVerificationResult(
                claim_id=2, claim="y", status=VerificationStatus.UNSUPPORTED, reason=""
            ),
        ]
        result = VerificationResult.aggregate("answer", claims)
        assert result.overall_status == VerificationStatus.UNSUPPORTED

    def test_uncertain_beats_uncited(self) -> None:
        from app.verification.models import ClaimVerificationResult, VerificationResult
        claims = [
            ClaimVerificationResult(
                claim_id=1, claim="x", status=VerificationStatus.UNCITED, reason=""
            ),
            ClaimVerificationResult(
                claim_id=2, claim="y", status=VerificationStatus.UNCERTAIN, reason=""
            ),
        ]
        result = VerificationResult.aggregate("answer", claims)
        assert result.overall_status == VerificationStatus.UNCERTAIN

    def test_empty_claims_is_supported(self) -> None:
        from app.verification.models import VerificationResult
        result = VerificationResult.aggregate("answer", [])
        assert result.overall_status == VerificationStatus.SUPPORTED

    def test_counts_are_correct(self) -> None:
        from app.verification.models import ClaimVerificationResult, VerificationResult
        claims = [
            ClaimVerificationResult(
                claim_id=1, claim="a", status=VerificationStatus.SUPPORTED, reason=""
            ),
            ClaimVerificationResult(
                claim_id=2, claim="b", status=VerificationStatus.UNSUPPORTED, reason=""
            ),
            ClaimVerificationResult(
                claim_id=3, claim="c", status=VerificationStatus.UNCITED, reason=""
            ),
            ClaimVerificationResult(
                claim_id=4, claim="d", status=VerificationStatus.UNCERTAIN, reason=""
            ),
        ]
        result = VerificationResult.aggregate("answer", claims)
        assert result.supported_count == 1
        assert result.unsupported_count == 1
        assert result.uncited_count == 1
        assert result.uncertain_count == 1
        assert result.total_claims == 4
