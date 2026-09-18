"""
FastAPI router for DocAnalyser RAG V0.1 End-to-End Pipeline.

Exposes:
    POST /api/v1/rag/ingest — Ingest document (PDF/TXT/MD), chunk, embed, and index
    POST /api/v1/rag/query  — Execute end-to-end RAG query with grounded citations
"""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.pipeline.models import IngestionResponse, RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import (
    IngestionError,
    QueryPipelineError,
    RAGPipeline,
    create_rag_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    """Return active RAGPipeline instance, initializing default if not set."""
    global _pipeline
    if _pipeline is None:
        _pipeline = create_rag_pipeline()
    return _pipeline


def set_pipeline(pipeline: Optional[RAGPipeline]) -> None:
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
    file: Optional[UploadFile] = File(default=None),
    file_path: Optional[str] = Form(default=None),
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
                return pipeline.ingest(tmp_path)
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
            return pipeline.ingest(path)
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
        logger.error("Unexpected error during RAG query: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred processing the RAG query.",
        ) from exc
