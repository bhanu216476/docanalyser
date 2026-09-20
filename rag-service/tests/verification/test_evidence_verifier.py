"""
Unit tests for MockEvidenceVerifier and verification models.

Tests:
- Preset status verifier always returns configured status
- Heuristic: evidence contains claim → SUPPORTED
- Heuristic: evidence does not contain claim → UNCERTAIN
- verify_multi: combines evidence items
- SemanticVerificationOutcome structure
- LLMEvidenceVerifier JSON parsing and rejection of malformed responses
- VerificationStatus enum values
- VerificationMode enum values
"""

from __future__ import annotations

import json
import pytest

from app.verification.evidence_verifier import (
    MockEvidenceVerifier,
    LLMEvidenceVerifier,
    SemanticVerificationOutcome,
)
from app.verification.models import (
    VerificationStatus,
    VerificationMode,
    VerificationPolicy,
)


class TestMockEvidenceVerifierPreset:
    """Tests with a preset status."""

    def test_preset_supported(self) -> None:
        verifier = MockEvidenceVerifier(
            preset_status=VerificationStatus.SUPPORTED,
            preset_confidence=0.95,
        )
        outcome = verifier.verify("any claim", "any evidence")
        assert outcome.status == VerificationStatus.SUPPORTED
        assert outcome.confidence == 0.95

    def test_preset_unsupported(self) -> None:
        verifier = MockEvidenceVerifier(preset_status=VerificationStatus.UNSUPPORTED)
        outcome = verifier.verify("any claim", "any evidence")
        assert outcome.status == VerificationStatus.UNSUPPORTED

    def test_preset_uncertain(self) -> None:
        verifier = MockEvidenceVerifier(preset_status=VerificationStatus.UNCERTAIN)
        outcome = verifier.verify("any claim", "any evidence")
        assert outcome.status == VerificationStatus.UNCERTAIN

    def test_preset_is_deterministic(self) -> None:
        verifier = MockEvidenceVerifier(preset_status=VerificationStatus.SUPPORTED)
        r1 = verifier.verify("claim", "evidence")
        r2 = verifier.verify("claim", "evidence")
        assert r1.status == r2.status
        assert r1.confidence == r2.confidence


class TestMockEvidenceVerifierHeuristic:
    """Tests for the substring heuristic mode."""

    def test_heuristic_supported_when_evidence_contains_claim(self) -> None:
        verifier = MockEvidenceVerifier(use_substring_heuristic=True)
        outcome = verifier.verify(
            "employees receive 12 casual leave days",
            "Employees receive 12 casual leave days per year.",
        )
        assert outcome.status == VerificationStatus.SUPPORTED

    def test_heuristic_uncertain_when_no_match(self) -> None:
        verifier = MockEvidenceVerifier(use_substring_heuristic=True)
        outcome = verifier.verify(
            "employees receive 20 casual leave days",
            "Employees receive 12 casual leave days.",
        )
        assert outcome.status == VerificationStatus.UNCERTAIN

    def test_heuristic_case_insensitive(self) -> None:
        verifier = MockEvidenceVerifier(use_substring_heuristic=True)
        outcome = verifier.verify(
            "EMPLOYEES RECEIVE 12 CASUAL LEAVE DAYS",
            "employees receive 12 casual leave days",
        )
        assert outcome.status == VerificationStatus.SUPPORTED

    def test_verify_multi_combines_evidence(self) -> None:
        verifier = MockEvidenceVerifier(use_substring_heuristic=True)
        outcome = verifier.verify_multi(
            "employees receive 12 casual leave days",
            [
                "Sick leave policy details.",
                "Employees receive 12 casual leave days per year.",
            ],
        )
        assert outcome.status == VerificationStatus.SUPPORTED

    def test_latency_is_non_negative(self) -> None:
        verifier = MockEvidenceVerifier()
        outcome = verifier.verify("claim", "evidence")
        assert outcome.latency_ms >= 0.0

    def test_prompt_version_recorded(self) -> None:
        verifier = MockEvidenceVerifier(preset_status=VerificationStatus.SUPPORTED)
        outcome = verifier.verify("claim", "evidence")
        assert outcome.prompt_version is not None
        assert len(outcome.prompt_version) > 0


class TestLLMEvidenceVerifierParsing:
    """Tests for LLMEvidenceVerifier JSON parsing logic."""

    class _FakeProvider:
        """Simple fake that returns a pre-configured JSON string."""

        def __init__(self, response: str) -> None:
            self._response = response

        def generate_string(self, prompt_text: str) -> str:
            return self._response

    def _make_verifier(self, response: str) -> LLMEvidenceVerifier:
        return LLMEvidenceVerifier(
            llm_provider=self._FakeProvider(response),
        )

    def test_valid_supported_response(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "SUPPORTED", "reason": "Evidence matches.", "confidence": 0.95})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.SUPPORTED
        assert outcome.confidence == 0.95
        assert "Evidence matches" in outcome.reason

    def test_valid_unsupported_response(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "UNSUPPORTED", "reason": "Contradiction.", "confidence": 0.88})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.UNSUPPORTED

    def test_valid_uncertain_response(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "UNCERTAIN", "reason": "Ambiguous.", "confidence": 0.5})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.UNCERTAIN

    def test_malformed_json_returns_uncertain(self) -> None:
        v = self._make_verifier("this is not json at all")
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.UNCERTAIN
        assert "JSON" in outcome.reason or "json" in outcome.reason.lower()

    def test_invalid_status_returns_uncertain(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "TOTALLY_MADE_UP", "reason": "Oops.", "confidence": 0.5})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.UNCERTAIN

    def test_markdown_code_fences_stripped(self) -> None:
        raw = "```json\n" + json.dumps({"status": "SUPPORTED", "reason": "OK", "confidence": 0.9}) + "\n```"
        v = self._make_verifier(raw)
        outcome = v.verify("claim", "evidence")
        assert outcome.status == VerificationStatus.SUPPORTED

    def test_confidence_clamped_to_range(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "SUPPORTED", "reason": "OK", "confidence": 1.5})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.confidence == 1.0

    def test_missing_confidence_is_none(self) -> None:
        v = self._make_verifier(
            json.dumps({"status": "SUPPORTED", "reason": "OK"})
        )
        outcome = v.verify("claim", "evidence")
        assert outcome.confidence is None


class TestVerificationModels:
    """Tests for VerificationStatus and VerificationPolicy models."""

    def test_all_statuses_defined(self) -> None:
        assert VerificationStatus.SUPPORTED == "SUPPORTED"
        assert VerificationStatus.UNSUPPORTED == "UNSUPPORTED"
        assert VerificationStatus.UNCERTAIN == "UNCERTAIN"
        assert VerificationStatus.UNCITED == "UNCITED"
        assert VerificationStatus.INVALID_CITATION == "INVALID_CITATION"

    def test_all_modes_defined(self) -> None:
        assert VerificationMode.RULE_BASED == "rule_based"
        assert VerificationMode.LLM == "llm"
        assert VerificationMode.HYBRID == "hybrid"

    def test_policy_defaults(self) -> None:
        policy = VerificationPolicy()
        assert policy.enabled is True
        assert policy.mode == VerificationMode.RULE_BASED
        assert policy.fail_on_unsupported is False

    def test_policy_immutable(self) -> None:
        policy = VerificationPolicy()
        with pytest.raises(Exception):
            policy.enabled = False  # type: ignore[misc]

    def test_claim_verification_result_total_latency(self) -> None:
        from app.verification.models import ClaimVerificationResult
        r = ClaimVerificationResult(
            claim_id=1,
            claim="test",
            status=VerificationStatus.SUPPORTED,
            reason="ok",
            rule_check_latency_ms=5.0,
            semantic_latency_ms=10.0,
        )
        assert r.total_latency_ms == 15.0
