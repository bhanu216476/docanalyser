"""Orchestration for add, update, and delete document events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipeline.rag_pipeline import IngestionError, RAGPipeline


class DocumentLifecycleError(Exception):
    """Raised when a document lifecycle operation cannot be completed."""


class DocumentLifecycleService:
    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline

    def process(self, request: Any) -> dict[str, Any]:
        event = request.event.value
        document_id = request.document_id.strip()
        if event == "DOCUMENT_DELETED":
            self.pipeline.vector_store.delete_by_document_id(document_id)
            self.pipeline.bm25_index.remove_by_document_id(document_id)
            return {
                "success": True,
                "document_id": document_id,
                "event": request.event,
                "status": "PROCESSED",
            }

        source = Path(request.source_url)
        if not source.is_file():
            raise FileNotFoundError(
                f"Document source does not exist: {request.source_url}"
            )

        if event in ("DOCUMENT_ADDED", "DOCUMENT_UPDATED"):
            self.pipeline.vector_store.delete_by_document_id(document_id)
            self.pipeline.bm25_index.remove_by_document_id(document_id)

        try:
            lifecycle_metadata = dict(request.metadata or {})
            if request.content_type:
                lifecycle_metadata["content_type"] = request.content_type
            if request.version:
                lifecycle_metadata["version"] = request.version
            if request.updated_at:
                lifecycle_metadata["updated_at"] = request.updated_at
            response = self.pipeline.ingest(
                source,
                document_id=document_id,
                metadata=lifecycle_metadata,
            )
        except IngestionError as exc:
            raise DocumentLifecycleError(str(exc)) from exc
        return {
            "success": True,
            "document_id": document_id,
            "event": request.event,
            "status": "PROCESSED",
            "chunk_count": response.chunk_count,
        }
