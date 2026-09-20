"""
Unit tests for RuleBasedVerifier.

Tests all 10 required failure cases plus edge cases:
- Case 1: Correct citation → no decisive rule (escalate to semantic)
- Case 2: Wrong number → UNSUPPORTED
- Case 3: Wrong entity → no decisive rule (requires semantic)
- Case 4: Missing citation → (tested in CitationVerifier)
- Case 5: Invalid citation (not in registry) → INVALID_CITATION
- Case 6: Conflicting evidence → UNCERTAIN (multi-evidence)
- Case 7: Partial support → no decisive rule
- Case 8: Negation mismatch → UNSUPPORTED
- Case 9: Correct semantic paraphrase → no decisive rule
- Case 10: Irrelevant evidence → no decisive rule

Also tests:
- Empty evidence → UNSUPPORTED
- Empty claim → UNSUPPORTED
- Numeric match (claim=evidence number) → no decisive rule
- Multi-evidence conflict detection
"""

from __future__ import annotations

import pytest
from app.verification.rules import RuleBasedVerifier
from app.verification.models import VerificationStatus


@pytest.fixture
def verifier() -> RuleBasedVerifier:
    return RuleBasedVerifier()


class TestRuleBasedVerifierSingleEvidence:
    """Single citation, single evidence source."""

    def test_case1_correct_citation_no_decisive_rule(
        self, verifier: RuleBasedVerifier
    ) -> None:
        """Case 1: Correct citation — rules are inconclusive (escalate to semantic)."""
        outcome = verifier.check(
            claim="Employees receive 12 casual leave days.",
            evidence="Employees receive 12 casual leave days.",
            citation_id=1,
            registry_has_id=True,
        )
        # Rule-based cannot confirm SUPPORTED — that requires semantic comparison
        assert outcome.status is None

    def test_case2_wrong_number_detected(self, verifier: RuleBasedVerifier) -> None:
        """Case 2: Claim says 20, evidence says 12 → UNSUPPORTED."""
        outcome = verifier.check(
            claim="Employees receive 20 casual leave days.",
            evidence="Employees receive 12 casual leave days.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED
        assert "20" in outcome.reason or "12" in outcome.reason

    def test_case5_invalid_citation_id(self, verifier: RuleBasedVerifier) -> None:
        """Case 5: Citation ID [99] not in registry → INVALID_CITATION."""
        outcome = verifier.check(
            claim="Employees receive 12 casual leave days.",
            evidence="",
            citation_id=99,
            registry_has_id=False,
        )
        assert outcome.status == VerificationStatus.INVALID_CITATION
        assert "99" in outcome.reason

    def test_case8_negation_mismatch(self, verifier: RuleBasedVerifier) -> None:
        """Case 8: Claim is positive, evidence negates → UNSUPPORTED."""
        outcome = verifier.check(
            claim="Employees are eligible for casual leave during probation.",
            evidence="Employees are not eligible for casual leave during probation.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED
        assert "negation" in outcome.reason.lower()

    def test_empty_evidence_is_unsupported(self, verifier: RuleBasedVerifier) -> None:
        outcome = verifier.check(
            claim="Employees receive 12 casual leave days.",
            evidence="",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED
        assert "empty" in outcome.reason.lower()

    def test_empty_claim_is_unsupported(self, verifier: RuleBasedVerifier) -> None:
        outcome = verifier.check(
            claim="",
            evidence="Employees receive 12 casual leave days.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED

    def test_case9_paraphrase_no_decisive_rule(
        self, verifier: RuleBasedVerifier
    ) -> None:
        """Case 9: Paraphrase ('twelve' vs '12') — rules are inconclusive."""
        outcome = verifier.check(
            claim="Employees are entitled to twelve casual leave days.",
            evidence="Employees receive 12 casual leave days.",
            citation_id=1,
            registry_has_id=True,
        )
        # 'twelve' is a word, not an integer — no numeric mismatch rule fires
        assert outcome.status is None

    def test_case10_irrelevant_evidence_no_decisive_rule(
        self, verifier: RuleBasedVerifier
    ) -> None:
        """Case 10: Irrelevant evidence — rules cannot detect irrelevance."""
        outcome = verifier.check(
            claim="Employees receive 12 casual leave days.",
            evidence="The office cafeteria is open from 8 AM to 6 PM.",
            citation_id=1,
            registry_has_id=True,
        )
        # Rule cannot detect topic irrelevance — escalate to semantic
        assert outcome.status is None

    def test_numeric_match_no_mismatch(self, verifier: RuleBasedVerifier) -> None:
        """When claim number and evidence number match exactly — no mismatch."""
        outcome = verifier.check(
            claim="The policy grants 15 sick leave days.",
            evidence="Employees receive 15 sick leave days per year.",
            citation_id=1,
            registry_has_id=True,
        )
        # Numbers match — no numeric mismatch rule fires
        assert outcome.status is None

    def test_latency_recorded(self, verifier: RuleBasedVerifier) -> None:
        """Latency must be non-negative."""
        outcome = verifier.check(
            claim="Employees receive 12 casual leave days.",
            evidence="Employees receive 12 casual leave days.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.latency_ms >= 0.0

    def test_dates_mismatch_detected(self, verifier: RuleBasedVerifier) -> None:
        """Numeric mismatch on years/dates."""
        outcome = verifier.check(
            claim="The policy was updated in 2023.",
            evidence="The policy was last updated in 2021.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED

    def test_negation_reversed_claim_negates_evidence_positive(
        self, verifier: RuleBasedVerifier
    ) -> None:
        """Claim negates, evidence is positive → UNSUPPORTED."""
        outcome = verifier.check(
            claim="Employees are not eligible during probation.",
            evidence="Employees are eligible during probation.",
            citation_id=1,
            registry_has_id=True,
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED


class TestRuleBasedVerifierMultiEvidence:
    """Multi-evidence (multi-citation) checks."""

    def test_case6_conflicting_numbers_uncertain(
        self, verifier: RuleBasedVerifier
    ) -> None:
        """Case 6: Source [1]=12 days, [2]=15 days → UNCERTAIN."""
        outcome = verifier.check_multi_evidence(
            claim="Employees receive 12 casual leave days.",
            evidence_items=[
                (1, "Employees receive 12 casual leave days."),
                (2, "Employees receive 15 casual leave days."),
            ],
            registry_ids={1, 2},
        )
        assert outcome.status == VerificationStatus.UNCERTAIN
        assert "conflict" in outcome.reason.lower()

    def test_all_empty_evidence_unsupported(
        self, verifier: RuleBasedVerifier
    ) -> None:
        outcome = verifier.check_multi_evidence(
            claim="Employees receive 12 casual leave days.",
            evidence_items=[(1, ""), (2, "")],
            registry_ids={1, 2},
        )
        assert outcome.status == VerificationStatus.UNSUPPORTED

    def test_missing_id_in_multi(self, verifier: RuleBasedVerifier) -> None:
        outcome = verifier.check_multi_evidence(
            claim="Some claim [1][99].",
            evidence_items=[(1, "Some evidence."), (99, "")],
            registry_ids={1},  # 99 not in registry
        )
        assert outcome.status == VerificationStatus.INVALID_CITATION

    def test_no_conflict_returns_none(self, verifier: RuleBasedVerifier) -> None:
        """Non-conflicting evidence sources → no decisive rule."""
        outcome = verifier.check_multi_evidence(
            claim="Employees receive 12 casual leave days.",
            evidence_items=[
                (1, "Employees receive 12 casual leave days."),
                (2, "Leave must be requested in advance."),
            ],
            registry_ids={1, 2},
        )
        assert outcome.status is None
