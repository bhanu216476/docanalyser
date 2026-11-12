"""
Domain models for Multi-Document Intelligence in DocAnalyser RAG Platform.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.citations.models import GroundedCitation


class MultiDocComparisonRequest(BaseModel):
    """Request for cross-document comparison and conflict detection."""

    document_ids: list[str] = Field(
        ...,
        min_length=2,
        description="List of at least two document IDs to compare.",
    )
    query: str | None = Field(
        default=None,
        description="Specific question or aspect to compare across documents.",
    )
    focus_aspects: list[str] = Field(
        default_factory=list,
        description="Key aspects to compare (e.g. ['security', 'architecture', 'pricing']).",
    )

    model_config = ConfigDict(frozen=True)


class DocumentConflict(BaseModel):
    """Represents a contradiction or disagreement between documents."""

    topic: str = Field(..., description="Subject of the discrepancy.")
    description: str = Field(..., description="Explanation of conflicting statements.")
    source_documents: list[str] = Field(default_factory=list, description="Documents involved.")
    citations: list[int] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ComparisonDifference(BaseModel):
    """Specific feature or operational difference between compared documents."""

    aspect: str = Field(..., description="Aspect or dimension of difference.")
    document_positions: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from document_id to its position/statement.",
    )
    citations: list[int] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class MultiDocComparisonResponse(BaseModel):
    """Structured result of multi-document comparative synthesis."""

    compared_documents: list[dict[str, str]] = Field(
        default_factory=list,
        description="Metadata list of documents compared ({'document_id': ..., 'file_name': ...}).",
    )
    consolidated_summary: str = Field(
        ...,
        description="Consolidated overview synthesizing findings across all documents.",
    )
    common_themes: list[str] = Field(
        default_factory=list,
        description="Shared concepts or points of agreement.",
    )
    differences: list[ComparisonDifference] = Field(
        default_factory=list,
        description="Distinct differences or contrasts identified across sources.",
    )
    conflicts: list[DocumentConflict] = Field(
        default_factory=list,
        description="Explicit discrepancies or conflicting claims detected.",
    )
    comparison_matrix: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Tabular comparison matrix (dimension -> doc_name -> details).",
    )
    citations: list[GroundedCitation] = Field(
        default_factory=list,
        description="Verified source citations grounding the comparative analysis.",
    )

    model_config = ConfigDict(frozen=True)
