"""
End-to-end integration tests for Citation Mapping in the RAG pipeline.

Verifies:
- Complete flow: Document -> Ingest -> Context Builder -> Prompt -> LLM -> Answer with [1] -> Citation Mapper -> Verified Citations.
- Invalid citation scenario: LLM output citing [99] when only [1] exists is detected and handled per policy.
- No fake source metadata is ever created.
- High-level RAGPipeline query integration.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.context.context_builder import ContextBuilder
from app.context.models import ContextBuilderConfig
from app.citations.mapper import CitationMapper
from app.citations.models import CitationValidationPolicy, InvalidCitationError
from app.llm.prompt_builder import PromptBuilder
from app.llm.prompts.models import Prompt
from app.llm.providers import FakeLLMProvider, LLMResponse
from app.pipeline.demo_cli import generate_demo_pdf
from app.pipeline.models import RAGResponse
from app.pipeline.rag_pipeline import RAGPipeline, create_rag_pipeline


class CustomAnswerLLM:
    """Mock LLM provider returning a programmed text answer."""

    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text

    def generate(self, prompt: Prompt) -> LLMResponse:
        return LLMResponse(
            version=prompt.version,
            response_text=self.answer_text,
            latency_ms=10.0,
            prompt_tokens=50,
            model_id="mock-custom-llm",
        )


@pytest.fixture
def policy_pdf(tmp_path: Path) -> Path:
    """Generate a sample 2-page PDF for leave policies."""
    pdf_path = tmp_path / "leave_policy.pdf"
    generate_demo_pdf(pdf_path)
    return pdf_path


class TestCitationEndToEnd:
    """End-to-end integration tests for the citation subsystem."""

    def test_e2e_valid_citation_flow(self, policy_pdf: Path) -> None:
        """
        End-to-End Test (Section 25):
        Document -> Chunk -> Context Builder -> Citation [1]
        -> Prompt -> Mock LLM -> Answer with [1] -> Citation Mapper -> Structured Response.
        """
        # Step 1: Ingest document into in-memory pipeline
        mock_provider = CustomAnswerLLM(
            answer_text="Employees receive 12 casual leave days [1] per calendar year."
        )
        pipeline = create_rag_pipeline(
            in_memory=True,
            llm_provider=mock_provider,  # type: ignore[arg-type]
        )
        pipeline.ingest(policy_pdf)

        # Step 2: Query pipeline
        response: RAGResponse = pipeline.query("How many casual leave days do employees receive?")

        # Step 3: Verify structured response
        assert "12 casual leave days [1]" in response.answer
        assert len(response.citations) == 1

        citation = response.citations[0]
        assert citation.id == 1
        assert citation.citation_id == "[1]"
        assert "leave_policy.pdf" in citation.file_name or "leave_policy.pdf" in citation.document
        assert citation.chunk_id != ""

        # Verify metadata records clean validation
        assert "citation_validation" in response.metadata
        val_info = response.metadata["citation_validation"]
        assert val_info["valid"] is True
        assert val_info["citation_ids"] == [1]
        assert val_info["invalid_ids"] == []

    def test_e2e_invalid_citation_detected_and_warned(self, policy_pdf: Path) -> None:
        """
        Invalid Citation End-to-End Test (Section 26):
        Mock LLM outputs: 'Employees receive 12 casual leave days [99].'
        when only [1] exists in the registry.

        Verify:
        - Invalid citation [99] is detected.
        - Warning is recorded in metadata.
        - Output citations list contains NO fake metadata for [99].
        - Raw answer is preserved unmodified.
        """
        mock_provider = CustomAnswerLLM(
            answer_text="Employees receive 12 casual leave days [99]."
        )
        pipeline = create_rag_pipeline(
            in_memory=True,
            llm_provider=mock_provider,  # type: ignore[arg-type]
        )
        pipeline.ingest(policy_pdf)

        response: RAGResponse = pipeline.query("How many casual leave days do employees receive?")

        # Raw answer preserved
        assert response.answer == "Employees receive 12 casual leave days [99]."

        # Invalid citation [99] detected
        val_info = response.metadata.get("citation_validation", {})
        assert val_info.get("valid") is False
        assert 99 in val_info.get("invalid_ids", [])
        assert "citation_warnings" in response.metadata
        assert any("[99]" in w for w in response.metadata["citation_warnings"])

        # Never generate fake source metadata for [99]
        assert len(response.citations) == 0

    def test_e2e_invalid_citation_reject_policy_raises(self, policy_pdf: Path) -> None:
        """
        Verify that configuring CitationValidationPolicy.REJECT causes pipeline
        to raise an exception when unknown citations occur.
        """
        mock_provider = CustomAnswerLLM(
            answer_text="Employees receive 12 casual leave days [99]."
        )
        strict_mapper = CitationMapper(default_policy=CitationValidationPolicy.REJECT)
        pipeline = create_rag_pipeline(
            in_memory=True,
            llm_provider=mock_provider,  # type: ignore[arg-type]
            citation_mapper=strict_mapper,
        )
        pipeline.ingest(policy_pdf)

        with pytest.raises(InvalidCitationError) as exc_info:
            pipeline.query("How many casual leave days do employees receive?")

        assert exc_info.value.invalid_ids == [99]

    def test_e2e_multiple_citations_first_appearance_order(self, policy_pdf: Path) -> None:
        """
        Verify multi-citation response preserves first appearance order [2] then [1].
        """
        mock_provider = CustomAnswerLLM(
            answer_text="Sick leave is provided [2] and casual leave is 12 days [1]."
        )
        pipeline = create_rag_pipeline(
            in_memory=True,
            llm_provider=mock_provider,  # type: ignore[arg-type]
        )
        pipeline.ingest(policy_pdf)

        response: RAGResponse = pipeline.query("What are the leave allowances?")

        # Verify appearance order
        assert len(response.citations) >= 2
        assert response.citations[0].id == 2
        assert response.citations[1].id == 1
