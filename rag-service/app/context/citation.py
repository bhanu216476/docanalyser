"""
Citation model generator and metadata extractor.

Extracts structured citations and metadata from RetrievalResult or RerankedResult.
Ensures no metadata is fabricated or hallucinated when absent.
"""

from __future__ import annotations

import re
from typing import Any, Union
from app.retrieval.models import RetrievalResult
from app.reranking.models import RerankedResult
from app.context.models import Citation


def format_citation_id(index: int) -> str:
    """
    Format a 1-based index into a standard bracketed citation ID.

    Example:
        1 -> "[1]"
        2 -> "[2]"
    """
    if index < 1:
        raise ValueError(f"Citation index must be >= 1, got {index}")
    return f"[{index}]"


def extract_citation(
    result: Union[RetrievalResult, RerankedResult],
    citation_id: str,
) -> Citation:
    """
    Extract a Citation from a RetrievalResult or RerankedResult.

    Extracts:
        - chunk_id
        - document_id
        - source
        - file_name
        - file_type
        - page / page_number
        - section
        - chunk_index
        - custom metadata

    Does NOT fabricate non-existent metadata values.
    """
    chunk_id = result.chunk_id
    metadata = dict(result.metadata)

    # Document ID
    doc_id = (
        result.document_id
        or metadata.get("document_id")
        or (result.provenance.document_id if result.provenance else "")
        or ""
    )

    # Source path/URL
    source = (
        result.source
        or metadata.get("source")
        or (result.provenance.source if result.provenance else "")
        or ""
    )

    # File name
    file_name = (
        result.file_name
        or metadata.get("file_name")
        or (source.split("/")[-1].split("\\")[-1] if source else "")
    )

    # File type
    file_type = (
        result.file_type
        or metadata.get("file_type")
        or (result.provenance.file_type if result.provenance else "")
        or (file_name.split(".")[-1].lower() if "." in file_name else "")
    )

    # Page info: check provenance, direct attribute, then metadata
    page: int | None = None
    page_number: int | None = None

    if result.provenance:
        if result.provenance.page is not None:
            page = result.provenance.page
        if result.provenance.page_number is not None:
            page_number = result.provenance.page_number
        elif result.provenance.page_numbers:
            page_number = result.provenance.page_numbers[0]

    if page is None and "page" in metadata and isinstance(metadata["page"], int):
        page = metadata["page"]

    if page_number is None and "page_number" in metadata and isinstance(metadata["page_number"], int):
        page_number = metadata["page_number"]
    elif page_number is None and page is not None:
        page_number = page + 1

    # Section
    section = result.section or metadata.get("section")
    if not section and result.provenance and result.provenance.headings:
        section = result.provenance.headings[0]

    # Chunk index
    chunk_index = result.chunk_index
    if chunk_index is None and "chunk_index" in metadata and isinstance(metadata["chunk_index"], int):
        chunk_index = metadata["chunk_index"]

    # Integer ID and canonical document name
    cit_num: int | None = None
    m = re.search(r"\d+", citation_id)
    if m:
        cit_num = int(m.group(0))

    document = file_name or source or doc_id

    return Citation(
        id=cit_num,
        citation_id=citation_id,
        document=document,
        chunk_id=chunk_id,
        document_id=doc_id,
        source=source,
        file_name=file_name,
        file_type=file_type,
        page=page,
        page_number=page_number,
        section=section,
        chunk_index=chunk_index,
        metadata=metadata,
    )
