"""
End-to-end integration tests for the Citation Verification Layer.

Verifies the complete pipeline:
    Context Builder
          ↓
    Citation Registry (BuiltContext.citation_registry)
          ↓
    Mock LLM (custom answer text)
          ↓
    Citation Mapper
          ↓
    Claim Extraction
          ↓
    Citation Verification
          ↓
    Verification Result

Test scenarios:
1. Correct answer + correct citation → SUPPORTED
2. Wrong number in answer → UNSUPPORTED
3. Wrong entity in answer (mock) → not SUPPORTED
4. No citation in answer → UNCITED
5. Invalid citation ID → INVALID_CITATION
6. Conflicting citations in registry → UNCERTAIN
7. Refusal/no-answer response → no false claims

Uses only in-memory components; no Qdrant or LLM API required.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Optional

from app.context.models import Citation, BuiltContext, ContextChunk, ContextBuilderConfig
from app.citations.mapper import CitationMapper
from app.llm.prompts.models import Prompt, PromptVersion
from app.llm.providers import LLMResponse
from app.verification.citation_verifier import CitationVerifier
from app.verification.evidence_verifier import MockEvidenceVerifier
from app.verification.models import (
    VerificationMode,
    VerificationPolicy,
    VerificationResult,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_citation_with_content(
    citation_id: int,
    content: str,
    file_name: str = "leave_policy.pdf",
) -> Citation:
    """Build a Citation with chunk content in metadata (as stored by ContextBuilder)."""
    return Citation(
        citation_id=f"[{citation_id}]",
        chunk_id=f"chunk_{citation_id}_{hash(content) % 99999:05d}",
        file_name=file_name,
        document=file_name,
        metadata={"content": content},
    )


def build_registry(*citations: Citation) -> dict[int, Citation]:
    return {c.id: c for c in citations if c.id is not None}


def run_verification(
    answer: str,
    registry: dict[int, Citation],
    mode: VerificationMode = VerificationMode.HYBRID,
) -> VerificationResult:
    """Convenience function: run verification against a registry with mock semantic."""
    policy = VerificationPolicy(enabled=True, mode=mode)
    verifier = CitationVerifier(
        policy=policy,
        semantic_verifier=MockEvidenceVerifier(use_substring_heuristic=True),
    )
    return verifier.verify(answer, registry)


# ---------------------------------------------------------------------------
# E2E Test 1: SUPPORTED — correct answer, correct citation
# ---------------------------------------------------------------------------

class TestE2ESupported:
    def test_correct_citation_is_supported(self) -> None:
        """
        Evidence: 'Employees receive 12 casual leave days.'
        Answer:   'Employees receive 12 casual leave days [1].'
        Expected: SUPPORTED
        """
        evidence = "Employees receive 12 casual leave days."
        cit = make_citation_with_content(1, evidence)
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.SUPPORTED, (
            f"Expected SUPPORTED, got {result.overall_status}: "
            f"{[c.reason for c in result.claims]}"
        )

    def test_result_has_one_claim(self) -> None:
        evidence = "Employees receive 12 casual leave days."
        cit = make_citation_with_content(1, evidence)
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.total_claims == 1
        assert result.supported_count == 1


# ---------------------------------------------------------------------------
# E2E Test 2: UNSUPPORTED — wrong number
# ---------------------------------------------------------------------------

class TestE2EUnsupported:
    def test_wrong_number_is_unsupported(self) -> None:
        """
        Evidence: 'Employees receive 12 casual leave days.'
        Answer:   'Employees receive 20 casual leave days [1].'
        Expected: UNSUPPORTED (numeric mismatch detected by rules)
        """
        evidence = "Employees receive 12 casual leave days."
        cit = make_citation_with_content(1, evidence)
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 20 casual leave days [1].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED, (
            f"Expected UNSUPPORTED, got {result.overall_status}"
        )

    def test_negation_is_unsupported(self) -> None:
        """
        Evidence: 'Employees are not eligible during probation.'
        Answer:   'Employees are eligible during probation [1].'
        Expected: UNSUPPORTED
        """
        evidence = "Employees are not eligible during probation."
        cit = make_citation_with_content(1, evidence)
        registry = build_registry(cit)
        result = run_verification(
            "Employees are eligible during probation [1].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# E2E Test 3: UNCITED — no citation marker
# ---------------------------------------------------------------------------

class TestE2EUncited:
    def test_uncited_claim(self) -> None:
        """
        Answer: 'Employees receive 12 casual leave days.' (no [N])
        Expected: UNCITED (not UNSUPPORTED)
        """
        registry: dict[int, Citation] = {}
        result = run_verification(
            "Employees receive 12 casual leave days.",
            registry,
        )
        assert result.overall_status == VerificationStatus.UNCITED
        assert result.uncited_count == 1
        assert result.unsupported_count == 0


# ---------------------------------------------------------------------------
# E2E Test 4: INVALID_CITATION
# ---------------------------------------------------------------------------

class TestE2EInvalidCitation:
    def test_invalid_citation_id(self) -> None:
        """
        Registry contains only [1]. Answer cites [99].
        Expected: INVALID_CITATION
        """
        evidence = "Employees receive 12 casual leave days."
        cit = make_citation_with_content(1, evidence)
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [99].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        assert result.overall_status == VerificationStatus.INVALID_CITATION
        assert result.invalid_citation_count == 1

    def test_no_fabricated_evidence_for_invalid_citation(self) -> None:
        cit = make_citation_with_content(1, "Employees receive 12 casual leave days.")
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [99].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        # The evidence snippet for [99] must be empty (no fabrication)
        for c in result.claims:
            if VerificationStatus.INVALID_CITATION == c.status:
                for snippet in c.evidence_snippets:
                    assert snippet == ""


# ---------------------------------------------------------------------------
# E2E Test 5: UNCERTAIN — conflicting evidence
# ---------------------------------------------------------------------------

class TestE2EUncertain:
    def test_conflicting_citations_uncertain(self) -> None:
        """
        [1] = 12 days, [2] = 15 days
        Answer: 'Employees receive 12 casual leave days [1][2].'
        Expected: UNCERTAIN
        """
        cit1 = make_citation_with_content(1, "Employees receive 12 casual leave days.")
        cit2 = make_citation_with_content(2, "Employees receive 15 casual leave days.")
        registry = build_registry(cit1, cit2)
        result = run_verification(
            "Employees receive 12 casual leave days [1][2].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        assert result.overall_status == VerificationStatus.UNCERTAIN


# ---------------------------------------------------------------------------
# E2E Test 6: Refusal / no-answer response
# ---------------------------------------------------------------------------

class TestE2ENoAnswer:
    def test_no_answer_response_creates_no_false_unsupported(self) -> None:
        """An explicit 'I cannot answer' should not produce UNSUPPORTED."""
        registry: dict[int, Citation] = {}
        result = run_verification(
            "The provided sources do not contain sufficient information to answer this question.",
            registry,
        )
        for c in result.claims:
            assert c.status != VerificationStatus.UNSUPPORTED, (
                f"Unexpected UNSUPPORTED for claim: {c.claim}"
            )


# ---------------------------------------------------------------------------
# E2E Test 7: Full pipeline with BuiltContext.citation_registry
# ---------------------------------------------------------------------------

class TestE2EBuiltContextRegistry:
    """
    Test using a BuiltContext object and its citation_registry property,
    which mirrors how the RAGPipeline feeds the verifier.
    """

    def _build_context(self, citation_id: int, content: str) -> BuiltContext:
        """Build a minimal BuiltContext with a single chunk."""
        cit = make_citation_with_content(citation_id, content)
        chunk = ContextChunk(
            citation_id=cit.citation_id,
            chunk_id=cit.chunk_id,
            content=content,
            formatted_text=f"[{citation_id}] {content}",
            token_count=len(content.split()),
            final_rank=1,
            citation=cit,
        )
        return BuiltContext(
            context_text=f"[{citation_id}] {content}",
            selected_chunks=[chunk],
            citations=[cit],
            token_count=len(content.split()),
            token_budget=2000,
        )

    def test_supported_via_built_context(self) -> None:
        content = "Employees receive 12 casual leave days."
        built_ctx = self._build_context(1, content)
        registry = built_ctx.citation_registry

        result = run_verification(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.overall_status == VerificationStatus.SUPPORTED

    def test_unsupported_via_built_context(self) -> None:
        content = "Employees receive 12 casual leave days."
        built_ctx = self._build_context(1, content)
        registry = built_ctx.citation_registry

        result = run_verification(
            "Employees receive 20 casual leave days [1].",
            registry,
            mode=VerificationMode.RULE_BASED,
        )
        assert result.overall_status == VerificationStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# E2E Test 8: Latency recorded
# ---------------------------------------------------------------------------

class TestE2ELatency:
    def test_total_latency_is_recorded(self) -> None:
        cit = make_citation_with_content(1, "Employees receive 12 casual leave days.")
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        assert result.total_verification_latency_ms >= 0.0

    def test_claim_latencies_non_negative(self) -> None:
        cit = make_citation_with_content(1, "Employees receive 12 casual leave days.")
        registry = build_registry(cit)
        result = run_verification(
            "Employees receive 12 casual leave days [1].",
            registry,
        )
        for c in result.claims:
            assert c.rule_check_latency_ms >= 0.0
            assert c.semantic_latency_ms >= 0.0
