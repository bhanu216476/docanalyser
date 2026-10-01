"""
Data models for queued document ingestion jobs.

Pipeline position:
    HTTP request (API / caller)
        ↓
    IngestionJobRequest     ← validated submission unit
        ↓
    IngestionJobQueue
        ↓
    IngestionJob            ← observable record (status, timings, errors)
        ↓
    IngestionJobResponse    ← API projection (adds dedupe + queue metadata)

Design decisions:
    - ``IngestionOperation`` mirrors the document lifecycle operations that
      already exist in the service (add / update / delete), so the queued
      path reuses ``DocumentLifecycleService`` instead of duplicating it.
    - ``IngestionJob`` is frozen (immutable) consistent with the rest of the
      DocAnalyser Pydantic conventions; state changes create new instances
      via ``model_copy``.
    - Error information is captured on the record itself (``error`` and
      ``error_type``) so failed jobs are fully auditable through the API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class IngestionOperation(StrEnum):
    """Supported document ingestion operations."""

    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class IngestionJobStatus(StrEnum):
    """Observable lifecycle states of an ingestion job."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        """Return True when no further processing will occur for this state."""
        return self in (IngestionJobStatus.COMPLETED, IngestionJobStatus.FAILED)

    @property
    def is_active(self) -> bool:
        """Return True while the job is still queued or being processed."""
        return not self.is_terminal


class IngestionJobRequest(BaseModel):
    """
    Validated submission payload for a queued ingestion job.

    Attributes:
        operation:   ADD, UPDATE, or DELETE.
        document_id: Identifier of the target document (required).
        file_name:   Source file name. Required for ADD / UPDATE.
        source_url:  Path of the document on the shared filesystem.
                     Required for ADD / UPDATE; ignored for DELETE.
        content_type: Optional MIME type propagated to document metadata.
        metadata:    Optional caller metadata merged into document metadata.
        version:     Optional document version propagated to metadata.
        updated_at:  Optional ISO-8601 timestamp propagated to metadata.
    """

    operation: IngestionOperation = Field(
        ..., description="Ingestion operation to perform: ADD, UPDATE, or DELETE."
    )
    document_id: str = Field(
        ...,
        min_length=1,
        description="Deterministic identifier of the target document.",
    )
    file_name: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Source file name (required for ADD / UPDATE).",
    )
    source_url: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Path of the document on the shared filesystem.",
    )
    content_type: Optional[str] = Field(
        default=None, min_length=1, description="Optional MIME type."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata merged into the document metadata.",
    )
    version: Optional[str] = Field(
        default=None, min_length=1, description="Optional document version."
    )
    updated_at: Optional[str] = Field(
        default=None, min_length=1, description="Optional ISO-8601 update timestamp."
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("document_id")
    @classmethod
    def validate_document_id_not_blank(cls, value: str) -> str:
        """Reject whitespace-only document identifiers."""
        if not value.strip():
            raise ValueError("document_id must not be blank")
        return value

    @model_validator(mode="after")
    def validate_source_for_ingestion(self) -> "IngestionJobRequest":
        """Require a source path and file name for ADD / UPDATE operations."""
        if self.operation in (IngestionOperation.ADD, IngestionOperation.UPDATE):
            if not self.source_url:
                raise ValueError("source_url is required for ADD/UPDATE ingestion jobs")
            if not self.file_name:
                raise ValueError("file_name is required for ADD/UPDATE ingestion jobs")
        return self


class IngestionJob(BaseModel):
    """
    Immutable record of a queued ingestion job.

    The record carries everything needed to identify the document and the
    operation, plus the observable execution state used by status endpoints.
    """

    job_id: str = Field(..., min_length=1, description="Unique job identifier.")
    document_id: str = Field(..., min_length=1, description="Target document ID.")
    operation: IngestionOperation = Field(..., description="Requested operation.")
    status: IngestionJobStatus = Field(
        default=IngestionJobStatus.QUEUED, description="Current job state."
    )
    source_url: Optional[str] = Field(default=None)
    file_name: Optional[str] = Field(default=None)
    content_type: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=utc_now, description="Submission timestamp (UTC)."
    )
    started_at: Optional[datetime] = Field(
        default=None, description="Timestamp when processing started (UTC)."
    )
    finished_at: Optional[datetime] = Field(
        default=None, description="Timestamp when processing finished (UTC)."
    )
    chunk_count: int = Field(
        default=0, ge=0, description="Chunks indexed by a successful job."
    )
    error: Optional[str] = Field(
        default=None, description="Failure message when status is FAILED."
    )
    error_type: Optional[str] = Field(
        default=None, description="Exception class name when status is FAILED."
    )

    model_config = ConfigDict(frozen=True)

    @property
    def is_terminal(self) -> bool:
        """Return True when the job reached COMPLETED or FAILED."""
        return self.status.is_terminal


class IngestionJobResponse(IngestionJob):
    """
    API projection of an ingestion job.

    Adds submission-time information derived from the queue rather than
    stored on the immutable job record.
    """

    deduplicated: bool = Field(
        default=False,
        description=(
            "True when an identical active job already existed and this "
            "submission was coalesced into it."
        ),
    )
    queue_position: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based FIFO position while the job is QUEUED.",
    )
