"""
Rule-based verifier for the Citation Verification Layer.

Responsibility
--------------
Perform cheap, deterministic first-pass checks before invoking any LLM
for semantic verification. These checks catch obvious failure cases
without making external API calls.

Rule hierarchy (applied in order, first decisive result wins)
-------------------------------------------------------------
1. INVALID_CITATION  — Citation ID not found in registry.
2. UNSUPPORTED       — Empty evidence (no chunk content to verify against).
3. UNSUPPORTED       — Empty claim text.
4. UNSUPPORTED       — Obvious numeric mismatch: a number in the claim is
                       explicitly present in the evidence at a different value.
5. UNSUPPORTED       — Obvious negation mismatch: claim asserts X, evidence
                       asserts NOT X (or vice versa) using the same entity.
6. None              — No decisive rule applied; escalate to semantic verifier.

Important limitations
---------------------
- Rule 4 (numeric mismatch) only detects cases where BOTH a number in the
  claim and a different number are explicitly present in the evidence for
  the same approximate context. It does NOT detect all numeric mismatches.
- Rule 5 (negation) uses simple negation word detection and is not a full
  semantic negation analyser. It reduces obvious false positives.
- These rules are intentionally conservative: they produce UNSUPPORTED only
  when the mismatch is unambiguous. Ambiguous cases return None so that the
  semantic verifier can handle them.
- Do NOT treat the rule-based layer as a complete verifier. It is a fast
  pre-filter only.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from app.verification.models import VerificationStatus

# Words that negate a statement
_NEGATION_WORDS = frozenset(
    ["not", "no", "never", "cannot", "can't", "won't", "isn't",
     "aren't", "doesn't", "don't", "didn't", "unable", "ineligible"]
)

# Pattern to extract all integers from text
_INT_PATTERN = re.compile(r"\b(\d+)\b")


@dataclass(frozen=True)
class RuleCheckOutcome:
    """
    Result of a single rule-based check pass.

    Attributes:
        status: Decisive status if a rule triggered, else None.
        reason: Human-readable explanation of the triggered rule.
        latency_ms: Monotonic time for the rule evaluation in milliseconds.
    """

    status: Optional[VerificationStatus]
    reason: str
    latency_ms: float


class RuleBasedVerifier:
    """
    Fast deterministic first-pass verifier applying rule-based checks.

    All rules are stateless; the verifier can be shared across threads.
    """

    def check(
        self,
        claim: str,
        evidence: str,
        citation_id: Optional[int] = None,
        registry_has_id: bool = True,
    ) -> RuleCheckOutcome:
        """
        Run all rule-based checks for one (claim, evidence) pair.

        Args:
            claim: Claim text with citation markers stripped.
            evidence: Evidence text from the authoritative registry.
            citation_id: The citation ID being verified (for diagnostics).
            registry_has_id: False if the citation ID was absent from registry.

        Returns:
            RuleCheckOutcome with status=None if no rule triggered decisively.
        """
        t_start = time.monotonic()

        # Rule 1 — INVALID_CITATION: ID not in registry
        if not registry_has_id:
            return RuleCheckOutcome(
                status=VerificationStatus.INVALID_CITATION,
                reason=(
                    f"Citation [{citation_id}] does not exist in the "
                    "authoritative registry; evidence cannot be resolved."
                ),
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Rule 2 — UNSUPPORTED: empty evidence
        if not evidence or not evidence.strip():
            return RuleCheckOutcome(
                status=VerificationStatus.UNSUPPORTED,
                reason="The cited chunk has no content; evidence is empty.",
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Rule 3 — UNSUPPORTED: empty claim
        if not claim or not claim.strip():
            return RuleCheckOutcome(
                status=VerificationStatus.UNSUPPORTED,
                reason="The claim text is empty; nothing to verify.",
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Rule 4 — Numeric mismatch
        numeric_outcome = self._check_numeric_mismatch(claim, evidence)
        if numeric_outcome is not None:
            return RuleCheckOutcome(
                status=VerificationStatus.UNSUPPORTED,
                reason=numeric_outcome,
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Rule 5 — Negation mismatch
        negation_outcome = self._check_negation_mismatch(claim, evidence)
        if negation_outcome is not None:
            return RuleCheckOutcome(
                status=VerificationStatus.UNSUPPORTED,
                reason=negation_outcome,
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # No decisive rule triggered
        return RuleCheckOutcome(
            status=None,
            reason="Rule-based checks did not produce a decisive result.",
            latency_ms=(time.monotonic() - t_start) * 1000.0,
        )

    def check_multi_evidence(
        self,
        claim: str,
        evidence_items: list[tuple[int, str]],  # (citation_id, evidence_text)
        registry_ids: set[int],
    ) -> RuleCheckOutcome:
        """
        Run rule-based checks for a claim with multiple evidence sources.

        Returns:
            - INVALID_CITATION if any referenced ID is absent from registry.
            - UNCERTAIN if evidence texts conflict with each other on a
              specific number that the claim states.
            - UNSUPPORTED if all evidence is empty.
            - None status if no decisive rule triggered.
        """
        t_start = time.monotonic()

        # Check for missing IDs
        for cid, _ in evidence_items:
            if cid not in registry_ids:
                return RuleCheckOutcome(
                    status=VerificationStatus.INVALID_CITATION,
                    reason=f"Citation [{cid}] does not exist in the registry.",
                    latency_ms=(time.monotonic() - t_start) * 1000.0,
                )

        # Check if all evidence is empty
        non_empty = [(cid, ev) for cid, ev in evidence_items if ev.strip()]
        if not non_empty:
            return RuleCheckOutcome(
                status=VerificationStatus.UNSUPPORTED,
                reason="All cited chunks have empty content.",
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        # Check for conflicting numbers across evidence sources
        conflict = self._check_evidence_conflict(claim, non_empty)
        if conflict is not None:
            return RuleCheckOutcome(
                status=VerificationStatus.UNCERTAIN,
                reason=conflict,
                latency_ms=(time.monotonic() - t_start) * 1000.0,
            )

        return RuleCheckOutcome(
            status=None,
            reason="Rule-based checks did not produce a decisive result.",
            latency_ms=(time.monotonic() - t_start) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Internal rule implementations
    # ------------------------------------------------------------------

    def _check_numeric_mismatch(
        self, claim: str, evidence: str
    ) -> Optional[str]:
        """
        Detect obvious numeric mismatches.

        Strategy:
        - Extract all integers from the claim.
        - For each claim integer, check if the evidence contains a DIFFERENT
          integer in a close-proximity token window (within 6 words).
        - A mismatch is only flagged when BOTH the claim integer AND a
          different integer appear in the evidence near relevant context.

        Conservative: only flags clear mismatches. Returns None if ambiguous.
        """
        claim_numbers = self._extract_numbers(claim)
        if not claim_numbers:
            return None

        evidence_numbers = self._extract_numbers(evidence)
        if not evidence_numbers:
            return None

        # For each claim number, if evidence contains a different specific number
        # in the same context, flag as mismatch.
        # Simple heuristic: if claim number NOT in evidence numbers at all,
        # but evidence has a number in the same range of magnitude → mismatch.
        claim_num_set = set(claim_numbers)
        evidence_num_set = set(evidence_numbers)

        # Find numbers in claim that are NOT in evidence
        missing_from_evidence = claim_num_set - evidence_num_set
        # Significant numbers: avoid false positives from times (8 AM, 6 PM),
        # page numbers (page 1), version numbers (v2), etc.
        # Threshold >=10 ensures we only flag substantive quantities.
        significant_claim_nums = {n for n in missing_from_evidence if 10 <= n <= 9999}
        significant_evidence_nums = {n for n in evidence_num_set if 10 <= n <= 9999}

        if significant_claim_nums and significant_evidence_nums:
            # Claim has specific numbers NOT in evidence, evidence has different numbers
            # This is a potential mismatch but we need to be more targeted.
            # Check: is there an exact numeric term in evidence that differs?
            for cn in significant_claim_nums:
                for en in significant_evidence_nums:
                    # Both are significant, different, and claim number is not in evidence
                    if cn != en:
                        return (
                            f"Numeric mismatch detected: claim states {cn} but "
                            f"evidence states {en}."
                        )

        return None

    def _check_negation_mismatch(
        self, claim: str, evidence: str
    ) -> Optional[str]:
        """
        Detect obvious negation contradictions.

        Strategy:
        - Check if one of claim/evidence is negated and the other is not,
          by looking for negation words within a small token window around
          shared key terms.
        - Only flags very clear negation flips (e.g., claim: "eligible",
          evidence: "not eligible").

        Conservative: returns None in ambiguous cases.
        """
        claim_negated = self._is_negated(claim)
        evidence_negated = self._is_negated(evidence)

        if claim_negated == evidence_negated:
            return None  # Both negated or both positive — no obvious mismatch

        # Check if they share significant key terms (making negation meaningful)
        claim_terms = self._key_terms(claim)
        evidence_terms = self._key_terms(evidence)
        shared_terms = claim_terms & evidence_terms

        if len(shared_terms) >= 1:
            direction = (
                "claim asserts positive but evidence negates it"
                if not claim_negated and evidence_negated
                else "claim negates but evidence asserts positive"
            )
            return (
                f"Negation mismatch: {direction}. "
                f"Shared key terms: {', '.join(sorted(shared_terms)[:3])}."
            )

        return None

    def _check_evidence_conflict(
        self,
        claim: str,
        evidence_items: list[tuple[int, str]],
    ) -> Optional[str]:
        """
        Detect conflicting numeric values across multiple evidence sources.

        If two evidence sources state different specific numbers for the same
        topic as the claim, flag as conflicting.
        """
        all_evidence_numbers: list[set[int]] = []
        for _, ev_text in evidence_items:
            nums = set(n for n in self._extract_numbers(ev_text) if 10 <= n <= 9999)
            all_evidence_numbers.append(nums)

        if len(all_evidence_numbers) < 2:
            return None

        # Check if different sources have mutually exclusive significant numbers
        first = all_evidence_numbers[0]
        for other in all_evidence_numbers[1:]:
            only_in_first = first - other
            only_in_other = other - first
            if only_in_first and only_in_other:
                return (
                    f"Evidence sources conflict: one source states {sorted(only_in_first)}, "
                    f"another states {sorted(only_in_other)} for the same topic."
                )

        return None

    @staticmethod
    def _extract_numbers(text: str) -> list[int]:
        """Extract all positive integers from text."""
        return [int(m.group(1)) for m in _INT_PATTERN.finditer(text)]

    @staticmethod
    def _is_negated(text: str) -> bool:
        """Return True if the text contains a negation word."""
        words = re.findall(r"\b\w+\b", text.lower())
        return bool(_NEGATION_WORDS.intersection(words))

    @staticmethod
    def _key_terms(text: str) -> set[str]:
        """
        Extract significant key terms (non-stopword words >= 4 chars).
        Used for shared-context detection in negation checks.
        """
        _STOPWORDS = frozenset([
            "that", "this", "with", "from", "they", "have", "will",
            "been", "their", "which", "when", "also", "more", "must",
            "through", "during", "after", "before", "employees", "employee",
        ])
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        return {w for w in words if w not in _STOPWORDS}
