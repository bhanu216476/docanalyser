"""
Canonical document metadata model for DocAnalyser ingestion pipeline.

Aligns with the Spring Boot Document entity and PostgreSQL documents table.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(str, Enum):
    """
    Controlled set of lifecycle states for a document in the ingestion pipeline.

    - PENDING: Document metadata recorded, awaiting chunking/embedding.
    - PROCESSED: Document successfully chunked, vectorized, and stored.
    - FAILED: Document processing encountered a terminal error.
    """

    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class DocumentMetadata(BaseModel):
    """
    Canonical, immutable document metadata model.

    Attributes:
        id: Unique database-generated identifier (UUID). None before persistence.
        file_name: Base name of the originating file (e.g. 'sample.txt').
        file_type: Normalized file type without dot, lowercase (e.g. 'txt', 'md').
        mime_type: Standard IANA MIME type (e.g. 'text/plain', 'text/markdown').
        source: Normalized source location/path.
        file_size: Size in bytes (non-negative integer).
        content_hash: SHA-256 hexadecimal digest of document content.
        status: Current ingestion status (defaults to PENDING).
        created_at: Time when record was created.
        updated_at: Time when record was last updated.
    """

    id: Optional[UUID] = Field(
        default=None,
        description="Unique document identifier (UUID).",
    )
    file_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Basename of the source file.",
    )
    file_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Canonical lowercase file extension without dot.",
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical IANA MIME type.",
    )
    source: str = Field(
        ...,
        min_length=1,
        description="Normalized source path or URI.",
    )
    file_size: int = Field(
        ...,
        ge=0,
        description="File size in bytes (non-negative).",
    )
    content_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Deterministic SHA-256 hash of document content.",
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        description="Current ingestion lifecycle status.",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp.",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp.",
    )

    model_config = ConfigDict(frozen=True)
