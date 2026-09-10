"""Common chunking service entrypoint for strategy selection."""

from typing import Any, Optional
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.chunking.fixed import fixed_chunk_documents
from app.chunking.recursive import recursive_chunk_documents
from app.chunking.semantic import semantic_chunk_documents


def chunk_documents(
    documents: list[Document],
    strategy: str = "fixed",
    config: Optional[dict[str, Any]] = None,
    embedding_model: Optional[Embeddings] = None
) -> list[Document]:
    """Chunk a list of Document objects using the specified strategy.

    Args:
        documents: List of LangChain Document objects to chunk.
        strategy: Chunking strategy to apply ("fixed", "recursive", "semantic").
        config: Dictionary containing strategy-specific parameters.
            For "fixed": chunk_size (int), chunk_overlap (int).
            For "recursive": chunk_size (int), chunk_overlap (int), separators (list).
            For "semantic": breakpoint_threshold_type (str), breakpoint_threshold_amount (float), buffer_size (int).
        embedding_model: Embedding model required if strategy is "semantic".

    Returns:
        List of Document chunks with normalized metadata.

    Raises:
        ValueError: If strategy is invalid or required parameters/models are missing.
    """
    if not isinstance(strategy, str) or not strategy.strip():
        raise ValueError(
            "strategy must be one of: 'fixed', 'recursive', 'semantic'"
        )

    cfg = config or {}
    norm_strategy = strategy.lower().strip()

    if norm_strategy == "fixed":
        chunk_size = cfg.get("chunk_size", 1000)
        chunk_overlap = cfg.get("chunk_overlap", 100)
        return fixed_chunk_documents(
            documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    elif norm_strategy == "recursive":
        chunk_size = cfg.get("chunk_size", 1000)
        chunk_overlap = cfg.get("chunk_overlap", 100)
        separators = cfg.get("separators", None)
        return recursive_chunk_documents(
            documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators
        )

    elif norm_strategy == "semantic":
        emb_model = embedding_model or cfg.get("embedding_model")
        if emb_model is None:
            raise ValueError("strategy 'semantic' requires an embedding_model to be provided")

        threshold_type = cfg.get("breakpoint_threshold_type", "percentile")
        threshold_amount = cfg.get("breakpoint_threshold_amount", 95.0)
        buffer_size = cfg.get("buffer_size", 1)

        return semantic_chunk_documents(
            documents,
            embedding_model=emb_model,
            breakpoint_threshold_type=threshold_type,
            breakpoint_threshold_amount=threshold_amount,
            buffer_size=buffer_size
        )

    else:
        raise ValueError(
            f"Unsupported chunking strategy: '{strategy}'. "
            "Supported strategies are: 'fixed', 'recursive', 'semantic'."
        )
