"""
Evidence verifier abstraction and implementations for the Citation Verification Layer.

Defines:
- EvidenceVerifier: Protocol that all semantic verifier implementations satisfy.
- MockEvidenceVerifier: Deterministic verifier for testing; never calls an LLM.
- LLMEvidenceVerifier: Semantic verifier backed by any LLMProvider.

Usage
-----
The CitationVerifier selects the appropriate EvidenceVerifier based on the
configured VerificationMode. Callers that only need rule-based verification
never instantiate a semantic verifier.

LLM Output Contract
-------------------
The LLMEvidenceVerifier requires the model to return a single JSON object:
    {"status": "<SUPPORTED|UNSUPPORTED|UNCERTAIN>", "reason": "...", "confidence": <float>}

Malformed or non-JSON responses are rejected with VerificationStatus.UNCERTAIN
and a diagnostic reason. The verifier never silently accepts an invalid response.

Security
--------
Claim and evidence texts are passed verbatim to the prompt builder which
applies explicit section delimiters. The verifier itself does not interpret
or execute any text from the claim or evidence.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional, Protocol, runtime_checkable

from app.verification.models import VerificationStatus
from app.verification.verification_prompt import (
    build_verification_prompt,
    build_multi_evidence_verification_prompt,
    VERIFICATION_PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

# Valid status strings accepted from LLM output
_VALID_LLM_STATUSES = frozenset(["SUPPORTED", "UNSUPPORTED", "UNCERTAIN"])


from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticVerificationOutcome:
    """
    Result of semantic evidence verification.

    Attributes:
        status: Verified status (SUPPORTED, UNSUPPORTED, or UNCERTAIN).
        reason: Human-readable explanation.
        confidence: Confidence score 0–1 from the verifier. NOT a calibrated probability.
        latency_ms: Monotonic wall-clock time for this verification call.
        prompt_version: Verification prompt version used.
    """

    status: VerificationStatus
    reason: str
    confidence: Optional[float]
    latency_ms: float
    prompt_version: str = VERIFICATION_PROMPT_VERSION


@runtime_checkable
class EvidenceVerifier(Protocol):
    """
    Protocol for semantic evidence verifiers.

    Any class implementing verify() satisfies this protocol.
    No inheritance required.
    """

    def verify(
        self,
        claim: str,
        evidence: str,
    ) -> SemanticVerificationOutcome:
        """
        Verify whether the claim is supported by the supplied evidence.

        Args:
            claim: Factual statement to verify (citation markers stripped).
            evidence: Evidence text from the authoritative citation registry.

        Returns:
            SemanticVerificationOutcome with status, reason, and confidence.
        """
        ...

    def verify_multi(
        self,
        claim: str,
        evidence_items: list[str],
    ) -> SemanticVerificationOutcome:
        """
        Verify a claim against multiple evidence sources.

        Args:
            claim: Factual statement to verify.
            evidence_items: List of evidence texts in citation order.

        Returns:
            SemanticVerificationOutcome aggregated across all evidence.
        """
        ...


class MockEvidenceVerifier:
    """
    Deterministic mock verifier for unit tests and CI.

    Never calls any external API. Returns a preset response for any input,
    or uses a simple heuristic (case-insensitive substring match) if no
    preset is configured.

    Args:
        preset_status: If set, always return this status regardless of input.
        preset_confidence: Confidence value for preset responses.
        use_substring_heuristic: If True and no preset, use simple substring
                                 matching: SUPPORTED if evidence contains
                                 the claim text (case-insensitive), else UNCERTAIN.
    """

    def __init__(
        self,
        preset_status: Optional[VerificationStatus] = None,
        preset_confidence: float = 0.9,
        use_substring_heuristic: bool = True,
    ) -> None:
        self._preset_status = preset_status
        self._preset_confidence = preset_confidence
        self._use_heuristic = use_substring_heuristic

    def verify(self, claim: str, evidence: str) -> SemanticVerificationOutcome:
        t_start = time.monotonic()

        if self._preset_status is not None:
            status = self._preset_status
            reason = f"Mock verifier returning preset status: {status.value}."
            confidence = self._preset_confidence
        elif self._use_heuristic:
            status, reason, confidence = self._heuristic(claim, evidence)
        else:
            status = VerificationStatus.UNCERTAIN
            reason = "Mock verifier: no preset and heuristic disabled."
            confidence = 0.5

        return SemanticVerificationOutcome(
            status=status,
            reason=reason,
            confidence=confidence,
            latency_ms=(time.monotonic() - t_start) * 1000.0,
        )

    def verify_multi(
        self, claim: str, evidence_items: list[str]
    ) -> SemanticVerificationOutcome:
        combined = "\n\n".join(evidence_items)
        return self.verify(claim, combined)

    @staticmethod
    def _heuristic(
        claim: str, evidence: str
    ) -> tuple[VerificationStatus, str, float]:
        """
        Simple substring heuristic for deterministic test responses.

        SUPPORTED  if evidence contains the claim text (case-insensitive).
        UNCERTAIN  otherwise.
        """
        claim_lower = claim.lower().strip()
        evidence_lower = evidence.lower()
        if claim_lower in evidence_lower:
            return (
                VerificationStatus.SUPPORTED,
                "Mock: evidence contains the claim text (substring match).",
                0.9,
            )
        return (
            VerificationStatus.UNCERTAIN,
            "Mock: evidence does not contain claim text; unable to determine support.",
            0.4,
        )


class LLMEvidenceVerifier:
    """
    Semantic evidence verifier backed by an LLM provider.

    Uses the versioned verification prompt (verification_prompt.py) to request
    structured JSON output from the model. Malformed responses are handled
    gracefully as UNCERTAIN rather than crashing.

    Args:
        llm_provider: Any object with a generate(prompt_text: str) -> str method,
                      OR an object with generate(prompt) -> LLMResponse.
                      Accepts raw string output for flexibility.
        model_id: Optional label for logging.
    """

    def __init__(
        self,
        llm_provider: object,
        model_id: str = "",
    ) -> None:
        self._provider = llm_provider
        self._model_id = model_id

    def verify(self, claim: str, evidence: str) -> SemanticVerificationOutcome:
        t_start = time.monotonic()
        prompt_text = build_verification_prompt(claim, evidence)
        raw_response = self._call_provider(prompt_text)
        outcome = self._parse_response(raw_response)
        latency_ms = (time.monotonic() - t_start) * 1000.0
        return SemanticVerificationOutcome(
            status=outcome[0],
            reason=outcome[1],
            confidence=outcome[2],
            latency_ms=latency_ms,
        )

    def verify_multi(
        self, claim: str, evidence_items: list[str]
    ) -> SemanticVerificationOutcome:
        t_start = time.monotonic()
        prompt_text = build_multi_evidence_verification_prompt(claim, evidence_items)
        raw_response = self._call_provider(prompt_text)
        outcome = self._parse_response(raw_response)
        latency_ms = (time.monotonic() - t_start) * 1000.0
        return SemanticVerificationOutcome(
            status=outcome[0],
            reason=outcome[1],
            confidence=outcome[2],
            latency_ms=latency_ms,
        )

    def _call_provider(self, prompt_text: str) -> str:
        """
        Call the underlying provider and extract a raw response string.

        Supports both:
        - Objects with generate(str) -> str
        - Objects with generate(Prompt) -> LLMResponse (existing project providers)
        """
        try:
            # Try duck-typed raw-string call first
            if callable(getattr(self._provider, "generate_raw", None)):
                return str(self._provider.generate_raw(prompt_text))  # type: ignore[union-attr]
            # Fallback: treat as existing LLMProvider — wrap in a minimal prompt
            result = self._provider.generate_string(prompt_text)  # type: ignore[union-attr]
            return str(result)
        except AttributeError:
            logger.warning(
                "LLMEvidenceVerifier: provider does not expose expected interface; "
                "returning UNCERTAIN."
            )
            return '{"status": "UNCERTAIN", "reason": "Provider interface error.", "confidence": 0.3}'

    def _parse_response(
        self, raw: str
    ) -> tuple[VerificationStatus, str, Optional[float]]:
        """
        Parse and validate the structured JSON response from the LLM.

        Rejects malformed responses rather than silently interpreting them.
        Returns UNCERTAIN for any parse or validation failure.
        """
        raw = raw.strip()
        # Strip any markdown code fences the model might have added
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Verification response is not valid JSON: %s — %s", raw[:200], exc)
            return (
                VerificationStatus.UNCERTAIN,
                f"Verification response was not valid JSON: {raw[:100]}",
                None,
            )

        if not isinstance(data, dict):
            logger.warning("Verification response is not a JSON object: %s", raw[:200])
            return (
                VerificationStatus.UNCERTAIN,
                "Verification response was not a JSON object.",
                None,
            )

        status_str = str(data.get("status", "")).strip().upper()
        if status_str not in _VALID_LLM_STATUSES:
            logger.warning("Invalid verification status in response: %r", status_str)
            return (
                VerificationStatus.UNCERTAIN,
                f"Invalid verification status returned by model: {status_str!r}.",
                None,
            )

        reason = str(data.get("reason", "")).strip() or "No reason provided."
        confidence_raw = data.get("confidence")
        confidence: Optional[float] = None
        if confidence_raw is not None:
            try:
                confidence = float(confidence_raw)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = None

        return (VerificationStatus(status_str), reason, confidence)
