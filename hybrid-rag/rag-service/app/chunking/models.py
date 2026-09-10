"""Data models and helpers for document chunking."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.documents import Document


def _normalize_page_numbers(page_numbers: Optional[list[int]]) -> Optional[list[int]]:
    """Remove duplicate page numbers while preserving source order."""
    if page_numbers is None:
        return None
    return list(dict.fromkeys(page_numbers))


class Chunk(BaseModel):
    """Represents a chunk extracted from a document."""

    chunk_id: str = Field(description="Unique identifier for the chunk")
    content: str = Field(description="Text content of the chunk")
    chunk_index: int = Field(description="0-based index of the chunk in the document")
    chunking_strategy: str = Field(description="Strategy used to produce chunk: fixed, recursive, semantic")
    total_chunks: Optional[int] = Field(default=None, description="Total chunks produced for the document")
    source: Optional[str] = Field(default=None, description="Document source path or URL")
    source_type: Optional[str] = Field(default=None, description="Document source type (pdf, html, etc.)")
    document_id: Optional[str] = Field(default=None, description="Parent document identifier if present")
    page: Optional[int] = Field(default=None, description="0-based page index")
    page_number: Optional[int] = Field(default=None, description="1-based page number")
    page_numbers: Optional[list[int]] = Field(default=None, description="List of page numbers covered by chunk")
    headings: list[str] = Field(default_factory=list, description="Extracted headings for document/section")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Preserved full original metadata")

    def to_document(self) -> Document:
        """Convert Chunk model to a LangChain Document with normalized metadata."""
        meta = dict(self.metadata)
        meta.update({
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "chunking_strategy": self.chunking_strategy,
        })
        if self.total_chunks is not None:
            meta["total_chunks"] = self.total_chunks
        if self.source is not None:
            meta["source"] = self.source
        if self.source_type is not None:
            meta["source_type"] = self.source_type
        if self.document_id is not None:
            meta["document_id"] = self.document_id
        if self.page is not None:
            meta["page"] = self.page
        if self.page_number is not None:
            meta["page_number"] = self.page_number
        normalized_page_numbers = _normalize_page_numbers(self.page_numbers)
        if normalized_page_numbers is not None:
            meta["page_numbers"] = normalized_page_numbers
            if normalized_page_numbers:
                meta["page_number"] = normalized_page_numbers[0]
                meta["page"] = normalized_page_numbers[0] - 1
        meta["headings"] = self.headings
        return Document(page_content=self.content, metadata=meta)


def build_chunk_document(
    content: str,
    orig_doc: Document,
    chunk_index: int,
    strategy: str,
    total_chunks: Optional[int] = None,
    spanned_page_numbers: Optional[list[int]] = None,
    doc_id: Optional[str] = None
) -> Document:
    """Build a LangChain Document for a chunk preserving original metadata.

    Args:
        content: Text content of the chunk.
        orig_doc: Original Document being chunked.
        chunk_index: Index of the chunk.
        strategy: Chunking strategy ("fixed", "recursive", "semantic").
        total_chunks: Optional total count of chunks.
        spanned_page_numbers: Optional list of page numbers spanned by the chunk.
        doc_id: Document ID if available.

    Returns:
        Document object with preserved and enriched metadata.
    """
    orig_meta = dict(orig_doc.metadata)

    # Base chunk id
    doc_identifier = doc_id or orig_meta.get("document_id") or orig_meta.get("source") or "doc"
    chunk_id = f"{doc_identifier}_chunk_{chunk_index}"

    new_meta = dict(orig_meta)
    new_meta["chunk_id"] = chunk_id
    new_meta["chunk_index"] = chunk_index
    new_meta["chunking_strategy"] = strategy

    if total_chunks is not None:
        new_meta["total_chunks"] = total_chunks

    if doc_identifier and "document_id" not in new_meta:
        new_meta["document_id"] = str(doc_identifier)

    page_numbers = _normalize_page_numbers(
        spanned_page_numbers if spanned_page_numbers is not None else orig_meta.get("page_numbers")
    )
    if page_numbers is not None:
        new_meta["page_numbers"] = page_numbers
        if page_numbers:
            new_meta["page_number"] = page_numbers[0]
            new_meta["page"] = page_numbers[0] - 1

    return Document(page_content=content, metadata=new_meta)
