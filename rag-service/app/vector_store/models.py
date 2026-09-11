"""
Data models and schema definitions for Qdrant vector storage.

Pipeline position:
    Chunk + Embedding
          ↓
    VectorPayload + VectorPoint   ← this module
          ↓
    QdrantVectorStore
          ↓
    Qdrant Collection
"""

from __future__ import annotations

from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ingestion.chunking.models import Chunk

# Fixed deterministic namespace for DocAnalyser point UUID generation (RFC 4122 v5)
DOCANALYSER_NAMESPACE = uuid.UUID("a7e1f480-1a74-4bc3-95c5-67be0bf1e5b2")


def generate_point_id(chunk_id: str) -> str:
    """
    Generate a deterministic UUID string for a chunk ID.

    Qdrant requires point IDs to be unsigned 64-bit integers or RFC 4122 UUID strings.
    If ``chunk_id`` is already a valid UUID string, returns it as-is.
    Otherwise, generates a deterministic UUIDv5 using the DocAnalyser namespace.

    Args:
        chunk_id: Source chunk identifier (e.g. '{document_id}:{chunk_index}').

    Returns:
        Deterministic 36-character hyphenated UUID string.
    """
    if not chunk_id or not chunk_id.strip():
        raise ValueError("chunk_id cannot be empty")

    try:
        # Check if already a valid UUID string
        parsed = uuid.UUID(chunk_id.strip())
        return str(parsed)
    except ValueError:
        # Generate deterministic UUIDv5
        return str(uuid.uuid5(DOCANALYSER_NAMESPACE, chunk_id.strip()))


class VectorPayload(BaseModel):
    """
    Canonical metadata payload stored alongside each vector point in Qdrant.

    Preserves source document traceability and chunk provenance.
    Enables direct retrieval of chunk text content without additional database lookups,
    while excluding full source document bodies to optimize vector store storage.

    Filterable fields:
        - document_id (keyword)
        - file_type (keyword)
        - source (keyword)
        - chunk_index (integer)
        - file_name (keyword)
    """

    document_id: str = Field(
        ...,
        min_length=1,
        description="Source document identifier.",
    )
    chunk_id: str = Field(
        ...,
        min_length=1,
        description="Original deterministic chunk identifier.",
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="0-based sequential index of the chunk within the document.",
    )
    file_name: str = Field(
        ...,
        min_length=1,
        description="Basename of the source document file.",
    )
    file_type: str = Field(
        ...,
        min_length=1,
        description="Canonical lowercase file extension (e.g. 'md', 'txt').",
    )
    source: str = Field(
        ...,
        min_length=1,
        description="Normalized source location or path.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the chunk (not the full document).",
    )
    start_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="Starting character offset in source document.",
    )
    end_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ending character offset in source document.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Section heading or title (e.g. from Markdown structure).",
    )
    headings: Optional[list[str]] = Field(
        default=None,
        description="Hierarchical heading path for Markdown chunks.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom chunk metadata.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        """Ensure content contains non-whitespace text."""
        if not v or not v.strip():
            raise ValueError("Payload content cannot be empty or whitespace only")
        return v


class VectorPoint(BaseModel):
    """
    Internal representation of a vector point to be upserted into Qdrant.

    Attributes:
        id:      Deterministic UUID string.
        vector:  Dense float vector.
        payload: Metadata payload dictionary.
    """

    id: str = Field(
        ...,
        description="Deterministic UUID string identifier for the point.",
    )
    vector: list[float] = Field(
        ...,
        min_length=1,
        description="Dense float embedding vector.",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Metadata payload associated with the vector point.",
    )

    model_config = ConfigDict(frozen=True)


def build_payload_from_chunk(chunk: Chunk) -> VectorPayload:
    """
    Construct a validated VectorPayload instance from a domain Chunk object.

    Args:
        chunk: The source Chunk instance.

    Returns:
        Validated immutable VectorPayload.
    """
    # Extract metadata fields from chunk
    meta = dict(chunk.metadata)
    file_name = str(meta.pop("file_name", "unknown"))
    file_type = str(meta.pop("file_type", "unknown"))
    source = str(meta.pop("source", "unknown"))
    section = meta.pop("section", None)
    headings = meta.pop("headings", None)

    # Pop non-custom or internal keys if present
    meta.pop("document_id", None)
    meta.pop("chunk_id", None)
    meta.pop("chunk_index", None)

    return VectorPayload(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        chunk_index=chunk.chunk_index,
        file_name=file_name,
        file_type=file_type,
        source=source,
        content=chunk.content,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        section=str(section) if section is not None else None,
        headings=list(headings) if headings is not None else None,
        metadata=meta,
    )
