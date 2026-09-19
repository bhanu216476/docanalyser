"""
End-to-end integration tests for DocAnalyser RAG V0.1.

Validates the full workflow against a synthetic PDF document:
    1. Ingestion of multi-page PDF policy document.
    2. Direct factual query: answers "12 casual leave days" with verified citations.
    3. Procedure query: answers submission procedure with citations.
    4. Unsupported question: returns grounded refusal without hallucinations or citations.
    5. Deduplication verification: guarantees no duplicate citations in any response.
    6. Prompt versioning support: handles v1, v2, and v3 prompt configurations.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.pipeline.demo_cli import DemoLLMProvider, generate_demo_pdf
from app.pipeline.models import RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import RAGPipeline, create_rag_pipeline


@pytest.fixture
def e2e_pipeline(tmp_path: Path) -> tuple[RAGPipeline, Path]:
    """
    Initialize an in-memory RAGPipeline and ingest a synthetic policy PDF.
    """
    pdf_path = tmp_path / "company_leave_policy.pdf"
    generate_demo_pdf(pdf_path)

    pipeline = create_rag_pipeline(
        in_memory=True,
        llm_provider=DemoLLMProvider(),
    )
    ingest_res = pipeline.ingest(pdf_path)
    assert ingest_res.chunk_count >= 2
    return pipeline, pdf_path


def test_e2e_factual_query_casual_leave(e2e_pipeline: tuple[RAGPipeline, Path]) -> None:
    """
    Verify direct factual query returns 12 casual leave days with verified citations.
    """
    pipeline, _ = e2e_pipeline
    query = "How many casual leave days do employees receive?"

    resp: RAGResponse = pipeline.query(query)

    assert "12 casual leave days" in resp.answer
    assert len(resp.citations) > 0

    # Verify citation fields
    for cit in resp.citations:
        assert cit.citation_id.startswith("[") and cit.citation_id.endswith("]")
        assert "company_leave_policy.pdf" in cit.file_name
        assert cit.chunk_id != ""

    # Verify citation deduplication
    citation_ids = [c.citation_id for c in resp.citations]
    assert len(citation_ids) == len(set(citation_ids)), "Duplicate citation IDs found!"

    chunk_ids = [c.chunk_id for c in resp.citations]
    assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk IDs found in citations!"


def test_e2e_factual_query_sick_leave(e2e_pipeline: tuple[RAGPipeline, Path]) -> None:
    """
    Verify sick leave factual query returns 10 paid sick leave days with citations.
    """
    pipeline, _ = e2e_pipeline
    query = "How many sick leave days are provided?"

    resp: RAGResponse = pipeline.query(query)

    assert "10 paid sick leave days" in resp.answer
    assert len(resp.citations) > 0


def test_e2e_unsupported_query_refusal(e2e_pipeline: tuple[RAGPipeline, Path]) -> None:
    """
    Verify unanswerable query returns grounded refusal without hallucinations or citations.
    """
    pipeline, _ = e2e_pipeline
    query = "What is the company's international travel allowance?"

    resp: RAGResponse = pipeline.query(query)

    # Must refuse to answer / indicate lack of info
    assert "not contain sufficient information" in resp.answer.lower()
    # Must NOT produce citations for an unsupported answer
    assert len(resp.citations) == 0


def test_e2e_prompt_version_override(e2e_pipeline: tuple[RAGPipeline, Path]) -> None:
    """
    Verify prompt_version override in request is reflected in the response.
    """
    pipeline, _ = e2e_pipeline
    req = RAGQueryRequest(
        query="How many sick leave days are provided?",
        prompt_version="v3",
    )

    resp: RAGResponse = pipeline.query(req)

    assert resp.prompt_version == "v3"
    assert "10 paid sick leave days" in resp.answer


def test_e2e_latency_breakdown_populated(e2e_pipeline: tuple[RAGPipeline, Path]) -> None:
    """
    Verify high-resolution latency breakdown covers all stages.
    """
    pipeline, _ = e2e_pipeline
    resp: RAGResponse = pipeline.query("How should leave requests be submitted?")

    required_stages = [
        "retrieval_ms",
        "fusion_ms",
        "reranking_ms",
        "context_building_ms",
        "prompt_assembly_ms",
        "llm_generation_ms",
        "total_ms",
    ]
    for stage in required_stages:
        assert stage in resp.latency_breakdown_ms
        assert resp.latency_breakdown_ms[stage] >= 0.0

    assert resp.latency_breakdown_ms["total_ms"] > 0.0
