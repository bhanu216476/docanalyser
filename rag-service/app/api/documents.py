"""Document lifecycle API used by the Spring orchestration service."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.pipeline.document_lifecycle import (
    DocumentLifecycleError,
    DocumentLifecycleService,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class DocumentLifecycleHandler(Protocol):
    def process(self, request: Any) -> dict[str, Any]: ...


_lifecycle_service: DocumentLifecycleHandler | None = None


class DocumentEvent(StrEnum):
    DOCUMENT_ADDED = "DOCUMENT_ADDED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"


class DocumentLifecycleRequest(BaseModel):
    event: DocumentEvent
    document_id: str = Field(..., min_length=1)
    file_name: str | None = Field(default=None, min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    content_type: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: str | None = Field(default=None, min_length=1)
    updated_at: str | None = Field(default=None, min_length=1)

    @field_validator("document_id")
    @classmethod
    def validate_document_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("document_id must not be blank")
        return value

    @model_validator(mode="after")
    def validate_source_for_ingestion(self) -> DocumentLifecycleRequest:
        if self.event in (DocumentEvent.DOCUMENT_ADDED, DocumentEvent.DOCUMENT_UPDATED):
            if not self.source_url:
                raise ValueError(
                    "source_url is required for document add/update events"
                )
            if not self.file_name:
                raise ValueError("file_name is required for document add/update events")
        return self


class DocumentLifecycleResponse(BaseModel):
    success: bool
    document_id: str
    event: DocumentEvent
    status: str
    chunk_count: int = 0


def get_document_lifecycle_service() -> DocumentLifecycleHandler:
    global _lifecycle_service
    if _lifecycle_service is None:
        from app.api.rag import get_pipeline

        _lifecycle_service = DocumentLifecycleService(get_pipeline())
    return _lifecycle_service


def set_document_lifecycle_service(
    service: DocumentLifecycleHandler | None,
) -> None:
    global _lifecycle_service
    _lifecycle_service = service


@router.post(
    "", response_model=DocumentLifecycleResponse, status_code=status.HTTP_200_OK
)
def process_document_event(
    request: DocumentLifecycleRequest,
) -> DocumentLifecycleResponse:
    try:
        result = get_document_lifecycle_service().process(request)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except DocumentLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        ) from exc
    return DocumentLifecycleResponse(**result)
