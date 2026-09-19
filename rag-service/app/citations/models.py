"""
Citation data models and validation structures for the Citation Mapping Layer.

Defines:
- CitationValidationPolicy: validation enforcement mode (warn or reject).
- CitationValidationResult: structured outcome of citation validation.
- GroundedCitation: clean, structured public citation representation.
- InvalidCitationError: exception raised when strict validation fails.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.context.models import Citation


class CitationValidationPolicy(str, Enum):
    """
    Policy for handling unknown or invalid citation IDs in generated answers.

    - WARN: Record validation issues in warnings/metadata, exclude invalid citations
            from structured output, but do not fail the request. Never fabricate source metadata.
    - REJECT: Hard fail with InvalidCitationError when invalid citations are detected.
    """

    WARN = "warn"
    REJECT = "reject"


class InvalidCitationError(ValueError):
    """Raised when an answer references citation IDs not present in the citation registry."""

    def __init__(self, invalid_ids: list[int], message: Optional[str] = None) -> None:
        self.invalid_ids = invalid_ids
        msg = message or f"Encountered invalid citation IDs not in registry: {invalid_ids}"
        super().__init__(msg)


class CitationValidationResult(BaseModel):
    """
    Structured outcome of validating parsed citations against an authoritative registry.

    Attributes:
        valid: True if all parsed citation IDs exist in the registry, False otherwise.
        citation_ids: All parsed citation IDs in order of first appearance.
        invalid_ids: Citation IDs that do not exist in the registry.
        duplicates: Citation IDs that were referenced more than once in the answer.
        warnings: Human-readable diagnostic warning messages.
    """

    valid: bool = Field(
        ...,
        description="Whether all citation references are valid and exist in the registry.",
    )
    citation_ids: list[int] = Field(
        default_factory=list,
        description="Unique citation IDs referenced in the answer (first appearance order).",
    )
    invalid_ids: list[int] = Field(
        default_factory=list,
        description="Citation IDs appearing in the answer that are absent from the registry.",
    )
    duplicates: list[int] = Field(
        default_factory=list,
        description="Citation IDs referenced multiple times in the answer.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings for invalid IDs or suspicious citation patterns.",
    )

    model_config = ConfigDict(frozen=True)


class GroundedCitation(BaseModel):
    """
    Public structured citation mapping an answer citation back to its verified source.

    Attributes:
        id: 1-based integer citation ID corresponding to [N] in the generated answer.
        document: Canonical document name or identifier.
        page: Optional 1-based page number if available in source metadata.
              Never fabricated if absent.
        chunk_id: Unique deterministic chunk identifier.
        document_id: Parent document identifier.
        source: Normalized source location or path.
        file_name: Base file name of source document.
        section: Document section or header if available.
        chunk_index: 0-based sequential chunk index within document.
        metadata: Additional custom metadata.
    """

    id: int = Field(
        ...,
        ge=1,
        description="1-based integer citation ID matching [N] in text.",
    )
    document: str = Field(
        ...,
        min_length=1,
        description="Canonical document name or source identifier.",
    )
    page: Optional[int] = Field(
        default=None,
        ge=1,
        description="Page number if present in authoritative source metadata.",
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="Deterministic chunk identifier from registry.",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Source document identifier.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Normalized source location or path.",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="Basename of source document.",
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
        description="Additional custom chunk metadata.",
    )

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_citation(
        cls,
        citation: Citation,
        id_override: Optional[int] = None,
    ) -> GroundedCitation:
        """
        Create a GroundedCitation from an authoritative Context Citation object.

        Guarantees:
        - Metadata is strictly extracted from the Citation object.
        - Page number is preserved if present; never fabricated.
        - Document identifier resolves from canonical fields (file_name, source, document_id).
        """
        # Resolve 1-based page: prefer page_number, then page + 1 (if 0-based page is known)
        page_val = citation.page_number
        if page_val is None and citation.page is not None:
            page_val = citation.page + 1

        # Resolve document name: prefer citation.document, then file_name, source, document_id
        doc_name = (
            citation.document
            or citation.file_name
            or citation.source
            or citation.document_id
            or "unknown_document"
        )

        resolved_id = id_override if id_override is not None else citation.id
        if resolved_id is None:
            digits = "".join(filter(str.isdigit, citation.citation_id))
            resolved_id = int(digits) if digits else 1

        return cls(
            id=resolved_id,
            document=doc_name,
            page=page_val,
            chunk_id=citation.chunk_id,
            document_id=citation.document_id or None,
            source=citation.source or None,
            file_name=citation.file_name or None,
            section=citation.section or None,
            chunk_index=citation.chunk_index,
            metadata=dict(citation.metadata),
        )

    def to_public_dict(self, include_extra: bool = False) -> dict[str, Any]:
        """
        Serialize to dictionary suitable for JSON responses.
        Omits 'page' if None to satisfy the rule:
        'If a document has no page metadata: {"id": 1, "document": "policy.txt"}'
        """
        data: dict[str, Any] = {
            "id": self.id,
            "document": self.document,
        }
        if self.page is not None:
            data["page"] = self.page

        if include_extra:
            if self.chunk_id:
                data["chunk_id"] = self.chunk_id
            if self.document_id:
                data["document_id"] = self.document_id
            if self.source:
                data["source"] = self.source
            if self.file_name:
                data["file_name"] = self.file_name
            if self.section:
                data["section"] = self.section
            if self.chunk_index is not None:
                data["chunk_index"] = self.chunk_index

        return data
