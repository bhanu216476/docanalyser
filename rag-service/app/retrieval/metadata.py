"""Metadata filtering and provenance extraction for dense retrieval."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.embeddings.models import EmbeddedChunk
from app.retrieval.models import RetrievalFilter, RetrievalProvenance


def matches_filter(candidate: EmbeddedChunk, filters: RetrievalFilter) -> bool:
    """Return whether a candidate satisfies every supplied filter."""
    metadata = candidate.metadata
    for field_name in ("document_id", "file_type", "source"):
        expected = getattr(filters, field_name)
        if expected is not None and metadata.get(field_name) != expected:
            return False

    if filters.page_number is not None and not _matches_page_number(
        metadata, filters.page_number
    ):
        return False
    return True


def extract_provenance(candidate: EmbeddedChunk) -> RetrievalProvenance:
    """Extract supported provenance fields without mutating candidate metadata."""
    metadata = candidate.metadata
    return RetrievalProvenance(
        document_id=_optional_string(metadata.get("document_id")),
        chunk_id=candidate.chunk_id,
        page=_optional_integer(metadata.get("page")),
        page_number=_optional_integer(metadata.get("page_number")),
        page_numbers=_copy_integer_list(metadata.get("page_numbers")),
        headings=_copy_string_list(metadata.get("headings")),
        source=_optional_string(metadata.get("source")),
        file_type=_optional_string(metadata.get("file_type")),
    )


def _matches_page_number(metadata: Mapping[str, Any], page_number: int) -> bool:
    """Match canonical 1-based page metadata, including spanned pages."""
    page_numbers = metadata.get("page_numbers")
    if isinstance(page_numbers, list) and page_number in page_numbers:
        return True
    if metadata.get("page_number") == page_number:
        return True
    return metadata.get("page") == page_number - 1


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _copy_integer_list(value: Any) -> list[int] | None:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        return None
    return list(value)


def _copy_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return list(value)
