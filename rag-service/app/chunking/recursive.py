"""Recursive character text splitting implementation."""

from typing import Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chunking.models import build_chunk_document


def recursive_chunk_documents(
    documents: list[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    separators: Optional[list[str]] = None
) -> list[Document]:
    """Split documents using recursive character text splitting.

    Args:
        documents: List of LangChain Document objects.
        chunk_size: Maximum chunk size (characters).
        chunk_overlap: Overlap between chunks (characters).
        separators: Custom hierarchical separators list. Defaults to ["\n\n", "\n", " ", ""].

    Returns:
        List of Document chunks with preserved metadata.

    Raises:
        ValueError: If chunk_size or chunk_overlap parameters are invalid.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be greater than 0, got {chunk_size}")
    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
        )

    kwargs = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    if separators is not None:
        kwargs["separators"] = separators

    splitter = RecursiveCharacterTextSplitter(**kwargs)
    pending_chunks: list[tuple[Document, str, str]] = []

    for doc_idx, doc in enumerate(documents):
        if not doc.page_content or not doc.page_content.strip():
            continue

        raw_chunks = splitter.split_text(doc.page_content)
        non_empty_chunks = [c for c in raw_chunks if c and c.strip()]
        parent_id = str(doc.metadata.get("document_id") or f"doc_{doc_idx}")
        pending_chunks.extend((doc, chunk_text, parent_id) for chunk_text in non_empty_chunks)

    parent_totals: dict[str, int] = {}
    parent_indices: dict[str, int] = {}
    for _, _, parent_id in pending_chunks:
        parent_totals[parent_id] = parent_totals.get(parent_id, 0) + 1

    all_chunks: list[Document] = []
    for doc, chunk_text, parent_id in pending_chunks:
        chunk_index = parent_indices.get(parent_id, 0)
        parent_indices[parent_id] = chunk_index + 1
        all_chunks.append(build_chunk_document(
            content=chunk_text,
            orig_doc=doc,
            chunk_index=chunk_index,
            strategy="recursive",
            total_chunks=parent_totals[parent_id],
            doc_id=parent_id
        ))

    return all_chunks
