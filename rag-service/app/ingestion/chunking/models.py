"""
Chunk data models for the ingestion chunking pipeline.

Represents the canonical representation of a document chunk ready for
downstream embedding generation and retrieval.

Pipeline position:
    Loader → Document → Chunking → Chunk → Embedding → Vector Store
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Chunk(BaseModel):
    """
    Canonical, immutable representation of a document chunk.

    Each chunk represents a discrete slice of text from a parent Document,
    retaining source attribution, deterministic ordering, and metadata
    for vector search and citation retrieval.

    Attributes:
        chunk_id:    Deterministic unique chunk identifier (e.g. '{document_id}:{chunk_index}').
        document_id: Identifier of the source document.
        content:     Non-empty text content of the chunk.
        chunk_index: 0-based sequential ordering index within the source document.
        start_char:  Starting character offset in the source document (if known).
        end_char:    Ending character offset in the source document (if known).
        metadata:    Arbitrary key-value metadata preserving source document properties,
                     heading hierarchy, and chunking parameters.
    """

    chunk_id: str = Field(
        ...,
        min_length=1,
        description="Deterministic unique chunk identifier (e.g. '{document_id}:{chunk_index}').",
    )
    document_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the source document.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Non-empty text content of this chunk.",
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="0-based sequential index of the chunk within the document.",
    )
    start_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="Starting character offset in the source document.",
    )
    end_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ending character offset in the source document.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata preserving source document attributes, section headers, and chunking parameters.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("content")
    @classmethod
    def validate_content_non_empty(cls, v: str) -> str:
        """Ensure content contains non-whitespace characters."""
        if not v or not v.strip():
            raise ValueError("Chunk content cannot be empty or whitespace only")
        return v

    @model_validator(mode="after")
    def validate_char_offsets(self) -> Chunk:
        """Ensure start_char <= end_char when both are provided."""
        if self.start_char is not None and self.end_char is not None:
            if self.start_char > self.end_char:
                raise ValueError(
                    f"start_char ({self.start_char}) cannot be greater than end_char ({self.end_char})"
                )
        return self

    @property
    def char_count(self) -> int:
        """Return the length of the chunk content in characters."""
        return len(self.content)
