"""
Data models for the Context Builder module and structured evidence context.

Defines:
- Citation: structured citation mapping evidence back to document source.
- ContextChunk: rich context item selected for the LLM context.
- ContextBuilderConfig: typed configuration for context budgeting and formatting.
- BuiltContext: final LLM-ready context with selected items, token metrics, and text.
- ContextItem: reranked evidence chunk model from origin/main.
- StructuredContext: ordered evidence context representation from origin/main.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.config import settings


class Citation(BaseModel):
    """
    Structured citation reference mapping LLM evidence back to source documents.

    Attributes:
        citation_id: Formatted citation tag (e.g., "[1]").
        chunk_id: Unique deterministic chunk identifier.
        document_id: Parent document identifier.
        source: Normalized source location or path.
        file_name: Base file name of source document.
        file_type: Canonical file extension (e.g. 'pdf', 'md', 'txt').
        page: Optional 0-based page index.
        page_number: Optional 1-based page number.
        section: Optional Markdown or document section heading.
        chunk_index: Optional sequential index within document.
        metadata: Additional custom chunk metadata.
    """

    citation_id: str = Field(
        ...,
        description="Formatted citation identifier, e.g. '[1]', '[2]'.",
    )
    chunk_id: str = Field(
        ...,
        description="Deterministic chunk identifier.",
    )
    document_id: str = Field(
        default="",
        description="Source document identifier.",
    )
    source: str = Field(
        default="",
        description="Normalized source location or path.",
    )
    file_name: str = Field(
        default="",
        description="Basename of the source document file.",
    )
    file_type: str = Field(
        default="",
        description="Canonical lowercase file extension.",
    )
    page: Optional[int] = Field(
        default=None,
        description="0-based page index if known.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based page number if known.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Document section or header.",
    )
    chunk_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based sequential chunk index within document.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom source metadata.",
    )

    model_config = ConfigDict(frozen=True)


class ContextChunk(BaseModel):
    """
    Selected chunk included in the LLM context.

    Preserves content, original/reranked scores, token footprint, and citation.
    """

    citation_id: str = Field(
        ...,
        description="Citation tag assigned to this chunk in the context.",
    )
    chunk_id: str = Field(
        ...,
        description="Unique chunk identifier.",
    )
    content: str = Field(
        ...,
        description="Evidence text content.",
    )
    formatted_text: str = Field(
        ...,
        description="Formatted evidence block including header, source info, and body.",
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="Token count of the formatted evidence block.",
    )
    final_rank: int = Field(
        ...,
        ge=1,
        description="1-based position in final context ordering.",
    )
    citation: Citation = Field(
        ...,
        description="Associated structured citation object.",
    )
    retrieval_score: Optional[float] = Field(
        default=None,
        description="Similarity or pre-reranking retrieval score if available.",
    )
    reranker_score: Optional[float] = Field(
        default=None,
        description="Reranker score if available.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Original chunk metadata.",
    )

    model_config = ConfigDict(frozen=True)


class ContextBuilderConfig(BaseModel):
    """
    Configuration options for context assembly.

    Attributes:
        token_budget: Maximum tokens allowed for the assembled context text.
        max_chunks: Maximum number of chunks to include, even if budget allows more.
        include_metadata: Whether to prepend source/page metadata in formatted chunk blocks.
        include_scores: Whether to display relevance scores in the formatted text.
        oversized_chunk_policy: 'skip' to drop chunks exceeding remaining budget,
                                'truncate' to truncate them to fit.
        deduplicate_content: Whether to deduplicate chunks that have identical normalized text
                             under different chunk IDs.
    """

    token_budget: int = Field(
        default_factory=lambda: settings.context_token_budget,
        ge=0,
        description="Total token budget for context.",
    )
    max_chunks: Optional[int] = Field(
        default_factory=lambda: settings.context_max_chunks,
        ge=1,
        description="Maximum number of evidence chunks to select.",
    )
    include_metadata: bool = Field(
        default_factory=lambda: settings.context_include_metadata,
        description="Whether to format source metadata into the evidence blocks.",
    )
    include_scores: bool = Field(
        default_factory=lambda: settings.context_include_scores,
        description="Whether to format retrieval scores into the evidence blocks.",
    )
    oversized_chunk_policy: Literal["skip", "truncate"] = Field(
        default_factory=lambda: settings.context_oversized_policy,  # type: ignore[arg-type]
        description="Action when a candidate chunk exceeds remaining token budget.",
    )
    deduplicate_content: bool = Field(
        default=True,
        description="Whether to detect and remove identical normalized content across different IDs.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("token_budget")
    @classmethod
    def validate_budget_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("token_budget cannot be negative")
        return v


class BuiltContext(BaseModel):
    """
    Final assembled context ready for injection into an LLM prompt.

    Attributes:
        context_text: The complete formatted context string.
        selected_chunks: List of structured ContextChunk items in order.
        citations: List of structured Citation objects corresponding to selected chunks.
        token_count: Actual total token count of the generated context_text.
        token_budget: Configured budget used for assembly.
        dropped_chunks_count: Number of candidate chunks skipped (due to duplicates,
                              token budget limits, or validation failures).
    """

    context_text: str = Field(
        ...,
        description="Combined LLM-ready context string.",
    )
    selected_chunks: list[ContextChunk] = Field(
        default_factory=list,
        description="Selected context chunks in final presentation order.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of structured citations for selected evidence.",
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="Total token count of context_text.",
    )
    token_budget: int = Field(
        ...,
        ge=0,
        description="Configured token budget limit.",
    )
    dropped_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of candidate chunks skipped or excluded.",
    )

    model_config = ConfigDict(frozen=True)


class ContextItem(BaseModel):
    """One reranked evidence chunk prepared for downstream generation."""

    position: int = Field(..., ge=1, description="1-based context position.")
    chunk_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    document_id: str = ""
    file_name: str = ""
    page_numbers: list[int] = Field(default_factory=list)
    section: str | None = None
    source: str = ""
    citation: str = Field(..., min_length=1)
    reranked_rank: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(frozen=True)

    @field_validator("chunk_id", "content")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        """Reject identifiers and evidence that contain no usable text."""

        if not value.strip():
            raise ValueError("value cannot be blank")
        return value

    @field_validator("page_numbers")
    @classmethod
    def validate_page_numbers(cls, value: list[int]) -> list[int]:
        """Require canonical page numbers to be positive integers."""

        if any(page < 1 for page in value):
            raise ValueError("page numbers must be positive")
        return value


class StructuredContext(BaseModel):
    """Ordered evidence and its prompt-ready representation."""

    items: list[ContextItem] = Field(default_factory=list)
    formatted_text: str = ""

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def item_count(self) -> int:
        """Return the number of evidence items in the context."""

        return len(self.items)
