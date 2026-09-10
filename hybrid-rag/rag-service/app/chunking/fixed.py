"""Fixed-size document chunking implementation."""

from langchain_core.documents import Document

from app.chunking.models import build_chunk_document


def fixed_chunk_documents(
    documents: list[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 100
) -> list[Document]:
    """Split documents into fixed-size character chunks with overlap.

    Args:
        documents: List of LangChain Document objects.
        chunk_size: Maximum character length per chunk (must be > 0).
        chunk_overlap: Number of overlapping characters between adjacent chunks (must be >= 0 and < chunk_size).

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

    pending_chunks: list[tuple[Document, str, str]] = []

    for doc_idx, doc in enumerate(documents):
        text = doc.page_content
        if not text or not text.strip():
            continue

        step = chunk_size - chunk_overlap
        doc_chunks: list[Document] = []
        text_length = len(text)

        # Slice text with sliding window
        start = 0
        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk_str = text[start:end]

            if chunk_str.strip():
                doc_chunks.append(chunk_str)

            if end == text_length:
                break
            start += step

        parent_id = str(doc.metadata.get("document_id") or f"doc_{doc_idx}")
        pending_chunks.extend((doc, chunk_text, parent_id) for chunk_text in doc_chunks)

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
            strategy="fixed",
            total_chunks=parent_totals[parent_id],
            doc_id=parent_id
        ))

    return all_chunks
