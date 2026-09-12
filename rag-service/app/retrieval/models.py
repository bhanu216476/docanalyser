"""
Data models for dense retrieval requests, filters, and results.

Pipeline position:
    HTTP Request
        ↓
    RetrievalRequest    ← validated input with query + top_k + filters
        ↓
    DenseRetriever / DenseRetrievalService
        ↓
    RetrievalResult[]   ← typed results with scores and chunk metadata

Design:
    - RetrievalFilter wraps the existing VectorStoreFilter fields and
      additionally supports page_number filtering.
    - RetrievalRequest enforces query non-emptiness and top_k bounds.
    - RetrievalResult preserves chunk identity, content, similarity score,
      metadata, rich source metadata, and typed provenance.
    - All models are frozen (immutable) consistent with project conventions.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class RetrievalFilter(BaseModel):
    """
    Optional metadata filter for dense retrieval.

    Multiple specified fields are combined with logical AND.

    Attributes:
        document_id:  Filter by one or more document IDs.
        file_type:    Filter by one or more file types (e.g. 'md', 'txt').
        source:       Filter by exact normalized source path.
        page_number:  Filter by 1-based page number.
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
        description=(
            "Filter by single file type or list of file types (e.g. 'md')."
        ),
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by exact normalized source path.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Filter by 1-based source page number.",
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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    @field_validator("document_id", "file_type", "source")
    @classmethod
    def validate_non_blank(
        cls,
        value: str | list[str] | None,
    ) -> str | list[str] | None:
        """Reject whitespace-only string filter values."""

        if value is None:
            return None

        values = value if isinstance(value, list) else [value]

        if any(not item.strip() for item in values):
            raise ValueError("filter values cannot be blank")

        return value

    @property
    def is_empty(self) -> bool:
        """Return True if no filter fields are set."""

        return all(
            value is None
            for value in (
                self.document_id,
                self.file_type,
                self.source,
                self.page_number,
                self.chunk_index,
                self.file_name,
                self.section,
            )
        )


class RetrievalRequest(BaseModel):
    """
    Validated dense retrieval request.

    Validation rules:
        - query: stripped; must not be empty after stripping.
        - top_k: must be >= 1 and <= settings.retrieval_max_top_k.
        - filters: optional metadata filters.
    """

    query: str = Field(
        ...,
        description=(
            "User search query. Stripped of whitespace; must not be empty."
        ),
    )
    top_k: int = Field(
        default=10,
        ge=1,
        description="Number of top similar chunks to retrieve.",
    )
    filters: Optional[RetrievalFilter] = Field(
        default=None,
        description="Optional metadata filters applied during retrieval.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("query", mode="before")
    @classmethod
    def strip_and_validate_query(cls, value: str) -> str:
        """Strip surrounding whitespace and reject empty queries."""

        if not isinstance(value, str):
            raise ValueError("query must be a string")

        stripped = value.strip()

        if not stripped:
            raise ValueError(
                "query cannot be empty or whitespace-only. "
                "Provide a meaningful search query."
            )

        return stripped

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k_upper_bound(cls, value: int) -> int:
        """Reject top_k values exceeding the configured maximum."""

        max_top_k = settings.retrieval_max_top_k

        if isinstance(value, int) and value > max_top_k:
            raise ValueError(
                f"top_k={value} exceeds the maximum allowed value of "
                f"{max_top_k}. Reduce top_k to avoid unbounded vector searches."
            )

        return value


class RetrievalProvenance(BaseModel):
    """Typed provenance extracted from a candidate's metadata."""

    document_id: str | None = None
    chunk_id: str
    page: int | None = None
    page_number: int | None = None
    page_numbers: list[int] | None = None
    headings: list[str] | None = None
    source: str | None = None
    file_type: str | None = None

    model_config = ConfigDict(frozen=True)


class RetrievalResult(BaseModel):
    """
    Dense retrieval result from an embedded chunk or Qdrant ScoredPoint.

    Preserves the source chunk's identity, content, similarity score,
    metadata, and provenance for downstream RAG stages.

    Score semantics:
        For Cosine distance: score ∈ [−1, 1] where 1.0 is identical.
        For Dot product: score is the raw dot product.
        For Euclidean distance: score is negated Euclidean distance.
        Results are returned in descending similarity order.
    """

    chunk_id: str = Field(
        ...,
        min_length=1,
        description="Original deterministic chunk identifier.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the chunk.",
    )
    score: float = Field(
        ...,
        description="Similarity score. Higher is more similar.",
    )
    rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based rank position in retrieval results.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom chunk metadata.",
    )

    # Rich source metadata used by the Qdrant/vector-store pipeline.
    document_id: str = Field(
        default="",
        description="Source document identifier.",
    )
    chunk_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based sequential index of chunk within document.",
    )
    file_name: str = Field(
        default="",
        description="Basename of the source document file.",
    )
    file_type: str = Field(
        default="",
        description="Canonical lowercase file extension.",
    )
    source: str = Field(
        default="",
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

    # Typed provenance extracted from metadata.
    provenance: RetrievalProvenance | None = None

    model_config = ConfigDict(frozen=True)

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        """Reject non-finite similarity scores."""

        if not math.isfinite(value):
            raise ValueError("score must be finite")

        return value