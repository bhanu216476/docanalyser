"""Semantic document chunking implementation using dependency-injected embeddings."""

import re
from typing import Any, Optional
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.chunking.models import build_chunk_document


_SUPPORTED_THRESHOLD_TYPES = {
    "percentile",
    "standard_deviation",
    "interquartile",
    "absolute",
}


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentence/paragraph units for semantic boundary evaluation."""
    if not text:
        return []
    # Split by paragraph double-newlines or sentence terminal punctuation followed by space/newline
    raw_units = re.split(r"(?<=[.?!])\s+|\n\n+", text)
    units = [u.strip() for u in raw_units if u and u.strip()]
    return units if units else ([text.strip()] if text.strip() else [])


def _cosine_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine distance between two vectors."""
    try:
        a = np.array(vec_a, dtype=float)
        b = np.array(vec_b, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Embedding vectors must contain numeric values") from exc
    if a.ndim != 1 or b.ndim != 1 or a.size == 0 or b.size == 0:
        raise ValueError("Embedding vectors must be non-empty one-dimensional vectors")
    if a.shape != b.shape:
        raise ValueError("Embedding vectors must have matching dimensions")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Embedding vectors must contain only finite values")
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    sim = np.dot(a, b) / (norm_a * norm_b)
    # Clip sim to [-1.0, 1.0] to prevent precision errors
    sim = max(-1.0, min(1.0, float(sim)))
    return 1.0 - sim


def _validate_embeddings(embeddings: list[list[float]], expected_count: int) -> None:
    """Validate the shape and values returned by an embedding provider."""
    if len(embeddings) != expected_count:
        raise ValueError(
            f"Embedding model returned {len(embeddings)} vectors; expected {expected_count}"
        )

    expected_dimension: Optional[int] = None
    for embedding in embeddings:
        try:
            vector = np.asarray(embedding, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding vectors must contain numeric values") from exc
        if vector.ndim != 1 or vector.size == 0:
            raise ValueError("Embedding vectors must be non-empty one-dimensional vectors")
        if not np.isfinite(vector).all():
            raise ValueError("Embedding vectors must contain only finite values")
        if expected_dimension is None:
            expected_dimension = vector.size
        elif vector.size != expected_dimension:
            raise ValueError("Embedding model returned vectors with mismatched dimensions")


def _calculate_breakpoint_threshold(
    distances: list[float],
    threshold_type: str,
    threshold_amount: float
) -> float:
    """Calculate distance threshold for semantic boundary detection."""
    if not distances:
        return 0.0

    arr = np.array(distances, dtype=float)

    if threshold_type == "percentile":
        amount = max(0.0, min(100.0, threshold_amount))
        return float(np.percentile(arr, amount))
    elif threshold_type == "standard_deviation":
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        return mean + (threshold_amount * std)
    elif threshold_type == "interquartile":
        q75, q25 = np.percentile(arr, [75, 25])
        iqr = q75 - q25
        return float(q75 + (threshold_amount * iqr))
    elif threshold_type == "absolute":
        return float(threshold_amount)
    else:
        raise ValueError(
            f"Unsupported breakpoint_threshold_type: '{threshold_type}'. "
            "Supported: 'percentile', 'standard_deviation', 'interquartile', 'absolute'"
        )


def semantic_chunk_documents(
    documents: list[Document],
    embedding_model: Embeddings,
    breakpoint_threshold_type: str = "percentile",
    breakpoint_threshold_amount: float = 95.0,
    buffer_size: int = 1
) -> list[Document]:
    """Split documents semantically based on embedding similarity of sentences/paragraphs.

    Args:
        documents: List of LangChain Document objects.
        embedding_model: Injected embedding model implementing Embeddings interface.
        breakpoint_threshold_type: Strategy for thresholding ('percentile', 'standard_deviation', 'interquartile', 'absolute').
        breakpoint_threshold_amount: Parameter amount for the threshold strategy (e.g. 95.0 for 95th percentile).
        buffer_size: Context buffer size around sentences when computing semantic distance.

    Returns:
        List of Document chunks grouped semantically with preserved metadata.

    Raises:
        ValueError: If embedding_model is None or breakpoint_threshold_type is invalid.
    """
    if breakpoint_threshold_type not in _SUPPORTED_THRESHOLD_TYPES:
        raise ValueError(
            f"Unsupported breakpoint_threshold_type: '{breakpoint_threshold_type}'. "
            "Supported: 'percentile', 'standard_deviation', 'interquartile', 'absolute'"
        )
    if buffer_size < 0:
        raise ValueError(f"buffer_size must be non-negative, got {buffer_size}")
    if embedding_model is None:
        raise ValueError("embedding_model must be provided for semantic chunking")

    pending_chunks: list[tuple[Document, str, str]] = []

    for doc_idx, doc in enumerate(documents):
        if not doc.page_content or not doc.page_content.strip():
            continue

        sentences = _split_into_sentences(doc.page_content)
        if not sentences:
            continue

        if len(sentences) == 1:
            parent_id = str(doc.metadata.get("document_id") or f"doc_{doc_idx}")
            pending_chunks.append((doc, sentences[0], parent_id))
            continue

        # Prepare text buffers for smoother semantic representation
        buffered_texts = []
        for i in range(len(sentences)):
            start_i = max(0, i - buffer_size)
            end_i = min(len(sentences), i + buffer_size + 1)
            buffered_texts.append(" ".join(sentences[start_i:end_i]))

        # Generate embeddings in batch
        embeddings = embedding_model.embed_documents(buffered_texts)
        _validate_embeddings(embeddings, len(buffered_texts))

        # Calculate distances between adjacent sentence embeddings
        distances: list[float] = []
        for i in range(len(embeddings) - 1):
            dist = _cosine_distance(embeddings[i], embeddings[i + 1])
            distances.append(dist)

        threshold = _calculate_breakpoint_threshold(
            distances, breakpoint_threshold_type, breakpoint_threshold_amount
        )

        # Group sentences into chunks based on threshold breakpoints
        current_chunk_sentences = [sentences[0]]
        grouped_chunks = []

        for i, dist in enumerate(distances):
            if dist > threshold:
                grouped_chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentences[i + 1]]
            else:
                current_chunk_sentences.append(sentences[i + 1])

        if current_chunk_sentences:
            grouped_chunks.append(" ".join(current_chunk_sentences))

        for idx, chunk_text in enumerate(grouped_chunks):
            if not chunk_text.strip():
                continue
            parent_id = str(doc.metadata.get("document_id") or f"doc_{doc_idx}")
            pending_chunks.append((doc, chunk_text, parent_id))

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
            strategy="semantic",
            total_chunks=parent_totals[parent_id],
            doc_id=parent_id
        ))

    return all_chunks
