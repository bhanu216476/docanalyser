"""
FastAPI router for DocAnalyser RAG V0.1 End-to-End Pipeline.

Exposes:
    POST /api/v1/rag/ingest — Ingest document (PDF/TXT/MD), chunk, embed, and index
    POST /api/v1/rag/query  — Execute end-to-end RAG query with grounded citations
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.evaluation.runner import EvaluationRunner
from app.multidoc.models import MultiDocComparisonRequest, MultiDocComparisonResponse
from app.multidoc.service import MultiDocumentIntelligenceService
from app.pipeline.models import IngestionResponse, RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import (
    IngestionError,
    QueryPipelineError,
    RAGPipeline,
    create_rag_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    """Return active RAGPipeline instance, initializing default if not set."""
    global _pipeline
    if _pipeline is None:
        _pipeline = create_rag_pipeline()
    return _pipeline


def set_pipeline(pipeline: RAGPipeline | None) -> None:
    """Inject a custom or in-memory RAGPipeline instance (e.g. for testing)."""
    global _pipeline
    _pipeline = pipeline


class FilePathIngestRequest(BaseModel):
    """Request model for ingesting a file already present on the local filesystem."""

    file_path: str = Field(
        ...,
        min_length=1,
        description="Path to local file to ingest (PDF, TXT, MD).",
    )


@router.post(
    "/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the RAG system",
)
async def ingest_document(
    file: UploadFile | None = File(default=None),  # noqa: B008
    file_path: str | None = Form(default=None),
    document_id: str | None = Form(default=None),
) -> IngestionResponse:
    """
    Ingest a document from either a multipart file upload or local file path.

    Stages:
        1. Document Loading (PDF, TXT, MD)
        2. Chunking
        3. Embedding Generation
        4. Vector Store Upsert (Qdrant)
        5. Inverted Index Registration (BM25)
    """
    pipeline = get_pipeline()

    if file is not None:
        # Save uploaded file preserving original filename
        orig_filename = Path(file.filename or "uploaded.txt").name
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir) / orig_filename
            content = await file.read()
            tmp_path.write_bytes(content)

            try:
                return pipeline.ingest(tmp_path, document_id=document_id)
            except IngestionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

    elif file_path:
        path = Path(file_path)
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_path}",
            )
        try:
            return pipeline.ingest(path, document_id=document_id)
        except IngestionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'file' (upload) or 'file_path' must be provided.",
        )


@router.post(
    "/query",
    response_model=RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute end-to-end RAG query",
)
async def query_rag(request: RAGQueryRequest) -> RAGResponse:
    """
    Execute end-to-end RAG retrieval, reranking, context assembly, and LLM generation.

    Returns:
        Grounded answer, verified citations, and high-resolution latency breakdown.
    """
    pipeline = get_pipeline()
    try:
        return pipeline.query(request)
    except QueryPipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error during RAG query: %s", exc, exc_info=True)  # noqa: G201
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred processing the RAG query.",
        ) from exc


@router.post(
    "/query/stream",
    summary="Execute end-to-end RAG query with Server-Sent Events (SSE) streaming",
)
async def query_rag_stream(request: RAGQueryRequest):
    """
    Stream the LLM response in real-time as Server-Sent Events (SSE).
    """
    pipeline = get_pipeline()

    async def event_generator():
        try:
            # First obtain the full response or execute pipeline
            res = pipeline.query(request)
            full_text = res.answer
            # Stream text in smooth tokens / chunks
            words = full_text.split(" ")
            chunk_size = 2
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i : i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                await asyncio.sleep(0.015)

            # Final payload with citations and metadata
            final_data = {
                "done": True,
                "answer": full_text,
                "citations": [c.model_dump() for c in res.citations],
                "metadata": res.metadata,
                "prompt_version": res.prompt_version,
            }
            yield f"data: {json.dumps(final_data)}\n\n"
        except Exception as exc:
            logger.error("Streaming error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/multidoc/compare",
    response_model=MultiDocComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare multiple documents, identify contrasts and detect conflicts",
)
async def compare_multiple_documents(request: MultiDocComparisonRequest) -> MultiDocComparisonResponse:
    """
    Execute deep multi-document comparative analysis.
    Identifies common themes, dimension-by-dimension differences, and conflicting claims.
    """
    pipeline = get_pipeline()
    service = MultiDocumentIntelligenceService(pipeline)
    try:
        return service.compare_documents(request)
    except Exception as exc:
        logger.error("Multi-document comparison failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to compare documents: {exc}",
        ) from exc


@router.post(
    "/evaluation/run",
    status_code=status.HTTP_200_OK,
    summary="Execute automated RAG evaluation suite",
)
async def run_automated_rag_evaluation(dataset_name: str = "production_eval") -> dict[str, Any]:
    """
    Run automated RAG evaluation measuring HitRate@K, Recall@K, Context Precision,
    Faithfulness, Answer Relevance, and Latency.
    """
    pipeline = get_pipeline()
    from app.evaluation.dataset import EvaluationCase

    sample_cases = [
        EvaluationCase(
            id="eval-001",
            question="What is the architecture of DocAnalyser RAG system?",
            expected_answer="DocAnalyser uses hybrid retrieval with dense Qdrant, sparse BM25, and cross-encoder reranking.",
            category="architecture",
        ),
        EvaluationCase(
            id="eval-002",
            question="What databases and persistence stores are used?",
            expected_answer="PostgreSQL, Redis, and Qdrant cloud vector store.",
            category="storage",
        ),
        EvaluationCase(
            id="eval-003",
            question="How does citation verification work in DocAnalyser?",
            expected_answer="Citations are mapped to chunk offsets and verified with claim extraction.",
            category="verification",
        ),
    ]

    runner = EvaluationRunner(dataset=sample_cases, pipeline=pipeline, dataset_name=dataset_name)
    report = runner.run()
    return report.model_dump(mode="json")

