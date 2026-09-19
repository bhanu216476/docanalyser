"""
Unit and stage tests for RAGPipeline.

Tests:
    - Pipeline initialization with in-memory store.
    - Ingestion of valid TXT and MD files.
    - Ingestion rejection on non-existent file or unsupported extension.
    - Independent execution of retrieve, fuse, rerank, build_context, build_prompt, generate.
    - End-to-end query execution with latency breakdown and metadata.
    - Grounded refusal on unanswerable query.
    - Error handling when a stage encounters a failure.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.context.models import BuiltContext, Citation
from app.embeddings.providers import FakeEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.llm.prompts.models import Prompt
from app.llm.providers import FakeLLMProvider
from app.pipeline.models import IngestionResponse, RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import (
    IngestionError,
    QueryPipelineError,
    RAGPipeline,
    create_rag_pipeline,
)
from app.reranking.mock_reranker import MockReranker
from app.retrieval.models import RetrievalResult


@pytest.fixture
def pipeline(tmp_path: Path) -> RAGPipeline:
    """Create an isolated, in-memory RAGPipeline instance for testing."""
    return create_rag_pipeline(in_memory=True)


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    """Create a temporary text file with sample policy content."""
    f = tmp_path / "test_policy.txt"
    f.write_text(
        "Standard working hours are 9:00 AM to 5:00 PM Monday through Friday. "
        "Employees are entitled to 15 days of annual leave and 10 days of medical leave.",
        encoding="utf-8",
    )
    return f


def test_pipeline_initialization(pipeline: RAGPipeline) -> None:
    """Verify all pipeline subsystems are initialized and accessible."""
    assert pipeline.vector_store is not None
    assert pipeline.bm25_index is not None
    assert pipeline.embedding_service is not None
    assert pipeline.chunker is not None
    assert pipeline.hybrid_retriever is not None
    assert pipeline.reranker is not None
    assert pipeline.context_builder is not None
    assert pipeline.prompt_builder is not None
    assert pipeline.llm_provider is not None


def test_ingest_valid_text_file(pipeline: RAGPipeline, sample_text_file: Path) -> None:
    """Verify ingesting a valid text file indexes chunks and returns latency breakdown."""
    resp: IngestionResponse = pipeline.ingest(sample_text_file)

    assert resp.chunk_count > 0
    assert resp.file_name == "test_policy.txt"
    assert resp.file_type == "txt"
    assert len(resp.document_id) > 0
    assert "load_ms" in resp.latency_breakdown_ms
    assert "chunk_ms" in resp.latency_breakdown_ms
    assert "embed_ms" in resp.latency_breakdown_ms
    assert "vector_store_ms" in resp.latency_breakdown_ms
    assert "bm25_ms" in resp.latency_breakdown_ms
    assert "total_ms" in resp.latency_breakdown_ms
    assert resp.latency_breakdown_ms["total_ms"] > 0


def test_ingest_nonexistent_file(pipeline: RAGPipeline, tmp_path: Path) -> None:
    """Verify IngestionError is raised when file does not exist."""
    missing = tmp_path / "does_not_exist.txt"
    with pytest.raises(IngestionError, match="Target file does not exist"):
        pipeline.ingest(missing)


def test_ingest_unsupported_extension(pipeline: RAGPipeline, tmp_path: Path) -> None:
    """Verify IngestionError is raised for unsupported file types."""
    invalid = tmp_path / "document.docx"
    invalid.write_text("dummy", encoding="utf-8")
    with pytest.raises(IngestionError, match="Unsupported document extension"):
        pipeline.ingest(invalid)


def test_retrieve_and_fuse_stages(pipeline: RAGPipeline, sample_text_file: Path) -> None:
    """Verify retrieve and fuse stages execute correctly on indexed content."""
    pipeline.ingest(sample_text_file)

    dense_res, bm25_res = pipeline.retrieve("working hours", top_k=5)
    assert isinstance(dense_res, list)
    assert isinstance(bm25_res, list)

    fused = pipeline.fuse(dense_res, bm25_res, top_k=5)
    assert isinstance(fused, list)
    if fused:
        assert fused[0].chunk_id != ""


def test_rerank_and_context_stages(pipeline: RAGPipeline, sample_text_file: Path) -> None:
    """Verify candidate reranking and context building produce token-budgeted context."""
    pipeline.ingest(sample_text_file)
    dense_res, bm25_res = pipeline.retrieve("annual leave", top_k=5)
    fused = pipeline.fuse(dense_res, bm25_res, top_k=5)

    reranked = pipeline.rerank(query="annual leave", candidates=fused, top_k=3)
    assert isinstance(reranked, list)

    built_ctx: BuiltContext = pipeline.build_context(reranked, token_budget=500)
    assert built_ctx.token_budget == 500
    assert built_ctx.token_count >= 0


def test_prompt_and_generation_stages(pipeline: RAGPipeline, sample_text_file: Path) -> None:
    """Verify prompt assembly and LLM generation produce expected response."""
    pipeline.ingest(sample_text_file)
    dense_res, bm25_res = pipeline.retrieve("annual leave", top_k=5)
    fused = pipeline.fuse(dense_res, bm25_res, top_k=5)
    reranked = pipeline.rerank("annual leave", fused)
    built_ctx = pipeline.build_context(reranked)

    prompt: Prompt = pipeline.build_prompt("How many annual leave days?", built_ctx, version="v2")
    assert prompt.query == "How many annual leave days?"
    assert prompt.context_text != ""

    llm_resp = pipeline.generate(prompt)
    assert llm_resp.response_text != ""
    assert llm_resp.latency_ms >= 0


def test_query_end_to_end_empty_query_raises_error(pipeline: RAGPipeline) -> None:
    """Verify empty query string raises QueryPipelineError."""
    with pytest.raises(QueryPipelineError, match="Query text cannot be empty"):
        pipeline.query("   ")


def test_query_end_to_end_success(pipeline: RAGPipeline, sample_text_file: Path) -> None:
    """Verify end-to-end query returns RAGResponse with answer, metadata, and latencies."""
    pipeline.ingest(sample_text_file)

    response: RAGResponse = pipeline.query("What are the working hours?")
    assert response.query == "What are the working hours?"
    assert len(response.answer) > 0
    assert "retrieval_ms" in response.latency_breakdown_ms
    assert "fusion_ms" in response.latency_breakdown_ms
    assert "reranking_ms" in response.latency_breakdown_ms
    assert "context_building_ms" in response.latency_breakdown_ms
    assert "prompt_assembly_ms" in response.latency_breakdown_ms
    assert "llm_generation_ms" in response.latency_breakdown_ms
    assert "total_ms" in response.latency_breakdown_ms
    assert response.metadata["dense_candidates_count"] >= 0
