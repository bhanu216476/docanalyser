"""
Data models for dense retrieval requests, filters, and results.

Pipeline position:
    HTTP Request
        ↓
    RetrievalRequest    ← validated input with query + top_k + filters
        ↓
    DenseRetriever
        ↓
    RetrievalResult[]   ← typed results with scores and chunk metadata

Design:
    - RetrievalFilter wraps the existing VectorStoreFilter fields without
      duplicating filter logic.  It is converted to VectorStoreFilter
      inside DenseRetriever before being sent to Qdrant.
    - RetrievalRequest enforces query non-emptiness and top_k bounds via
      Pydantic validators, consistent with the project's validation conventions.
    - RetrievalResult maps 1-to-1 from Qdrant ScoredPoint payloads using
      the VectorPayload schema already stored with each vector point.
    - All models are frozen (immutable) consistent with project conventions.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class RetrievalFilter(BaseModel):
    """
    Optional metadata filter for dense retrieval.

    Maps directly to the VectorStoreFilter fields indexed by Qdrant.
    Multiple specified fields are combined with logical AND.
    Filter push-down is performed inside Qdrant — not in Python.

    Attributes:
        document_id:  Filter by one or more document IDs.
        file_type:    Filter by one or more file types (e.g. 'md', 'txt').
        source:       Filter by exact normalized source path.
        chunk_index:  Filter by exact 0-based chunk index.
        file_name:    Filter by source file name.
        section:      Filter by Markdown section heading.
    """

    document_id: Optional[str | list[str]] = Field(
        default=None,
        description="Filter by single document ID or list of document IDs.",
    )
    file_type: Optional[str | list[str]] = Field(
        default=None,
        description="Filter by single file type or list of file types (e.g. 'md', 'txt').",
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by exact normalized source path.",
    )
    chunk_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Filter by exact 0-based chunk index.",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="Filter by source file name.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Filter by Markdown section heading.",
    )

    model_config = ConfigDict(frozen=True)

    @property
    def is_empty(self) -> bool:
        """Return True if no filter fields are set."""
        return all(
            v is None
            for v in (
                self.document_id,
                self.file_type,
                self.source,
                self.chunk_index,
                self.file_name,
                self.section,
            )
        )


class RetrievalRequest(BaseModel):
    """
    Validated dense retrieval request.

    Validation rules:
        - query: stripped of surrounding whitespace; must not be empty after stripping.
        - top_k: must be >= 1 and <= settings.retrieval_max_top_k (default 100).
        - filters: optional; all filter fields are optional individually.

    Attributes:
        query:   The user's search query string.
        top_k:   Number of nearest-neighbour chunks to retrieve.
        filters: Optional metadata filters pushed down to Qdrant.
    """

    query: str = Field(
        ...,
        description="User search query. Stripped of surrounding whitespace; must not be empty.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        description="Number of top similar chunks to retrieve. Must be >= 1.",
    )
    filters: Optional[RetrievalFilter] = Field(
        default=None,
        description="Optional metadata filters applied server-side in Qdrant.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("query", mode="before")
    @classmethod
    def strip_and_validate_query(cls, v: str) -> str:
        """Strip surrounding whitespace and reject empty/whitespace-only queries."""
        if not isinstance(v, str):
            raise ValueError("query must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError(
                "query cannot be empty or whitespace-only. "
                "Provide a meaningful search query."
            )
        return stripped

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k_upper_bound(cls, v: int) -> int:
        """Reject top_k that exceeds the configured maximum."""
        max_top_k = settings.retrieval_max_top_k
        if isinstance(v, int) and v > max_top_k:
            raise ValueError(
                f"top_k={v} exceeds the maximum allowed value of {max_top_k}. "
                f"Reduce top_k to avoid unbounded vector searches."
            )
        return v


class RetrievalResult(BaseModel):
    """
    A single dense retrieval result mapped from a Qdrant ScoredPoint.

    Preserves the source chunk's identity, content, similarity score,
    and metadata for downstream RAG stages.

    Score semantics:
        For Cosine distance: score ∈ [−1, 1] where 1.0 is identical.
        For Dot product: score is the raw dot product (unbounded above).
        For Euclidean distance: score is negated Euclidean distance.
        Results are returned in Qdrant's native ranking order (highest first).

    Attributes:
        chunk_id:    Original deterministic chunk identifier.
        score:       Qdrant similarity score for this result.
        document_id: Source document identifier.
        chunk_index: 0-based sequential chunk index within the document.
        content:     Chunk text content (stored in Qdrant payload).
        file_name:   Basename of the source document file.
        file_type:   Canonical lowercase file extension ('md', 'txt', etc.).
        source:      Normalized source path.
        section:     Markdown section heading (if available).
        start_char:  Start character offset in source document (if available).
        end_char:    End character offset in source document (if available).
        metadata:    Additional custom chunk metadata from the payload.
    """

    chunk_id: str = Field(
        ...,
        description="Original deterministic chunk identifier.",
    )
    score: float = Field(
        ...,
        description="Qdrant similarity score. Higher is more similar for Cosine/Dot.",
    )
    document_id: str = Field(
        ...,
        description="Source document identifier.",
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="0-based sequential index of the chunk within the document.",
    )
    content: str = Field(
        ...,
        description="Text content of the chunk.",
    )
    file_name: str = Field(
        ...,
        description="Basename of the source document file.",
    )
    file_type: str = Field(
        ...,
        description="Canonical lowercase file extension (e.g. 'md', 'txt').",
    )
    source: str = Field(
        ...,
        description="Normalized source location or path.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Markdown section heading or title.",
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
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom chunk metadata.",
    )

    model_config = ConfigDict(frozen=True)
