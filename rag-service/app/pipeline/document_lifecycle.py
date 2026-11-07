"""Orchestration for add, update, and delete document events."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.pipeline.rag_pipeline import IngestionError


class DocumentLifecycleError(Exception):
    """Raised when a document lifecycle operation cannot be completed."""


class LifecyclePipeline(Protocol):
    vector_store: Any
    bm25_index: Any
    ingest: Any


class DocumentLifecycleService:
    def __init__(self, pipeline: LifecyclePipeline) -> None:
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

        source_str = str(request.source_url or "").strip()
        is_remote = source_str.startswith(("http://", "https://"))

        if is_remote:
            import tempfile
            import httpx

            ext = Path(request.file_name or "document.txt").suffix or ".txt"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_source = Path(tmp.name)

            try:
                with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                    resp = client.get(source_str)
                    resp.raise_for_status()
                    tmp_source.write_bytes(resp.content)

                if event in ("DOCUMENT_ADDED", "DOCUMENT_UPDATED"):
                    self.pipeline.vector_store.delete_by_document_id(document_id)
                    self.pipeline.bm25_index.remove_by_document_id(document_id)

                lifecycle_metadata = dict(request.metadata or {})
                if request.content_type:
                    lifecycle_metadata["content_type"] = request.content_type
                if request.version:
                    lifecycle_metadata["version"] = request.version
                if request.updated_at:
                    lifecycle_metadata["updated_at"] = request.updated_at
                response = self.pipeline.ingest(
                    tmp_source,
                    document_id=document_id,
                    metadata=lifecycle_metadata,
                )
            except httpx.HTTPError as exc:
                raise DocumentLifecycleError(
                    f"Failed to fetch remote document from {source_str}: {exc}"
                ) from exc
            except IngestionError as exc:
                raise DocumentLifecycleError(str(exc)) from exc
            finally:
                if tmp_source.exists():
                    try:
                        tmp_source.unlink()
                    except OSError:
                        pass

            return {
                "success": True,
                "document_id": document_id,
                "event": request.event,
                "status": "PROCESSED",
                "chunk_count": response.chunk_count,
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

    async def process_async(self, request: Any) -> dict[str, Any]:
        """
        Async wrapper around :meth:`process`.

        Document loading, chunking, embedding and indexing are synchronous
        (filesystem, provider SDK, Qdrant client), so they are isolated in a
        worker thread instead of blocking the event loop. Behaviour and
        error semantics are identical to the synchronous implementation.
        """
        return await asyncio.to_thread(self.process, request)
