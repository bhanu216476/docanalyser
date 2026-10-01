"""Chunk-to-embedding orchestration without vector-store concerns."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document

from app.chunking.service import chunk_documents
from app.embeddings.models import EmbeddedChunk
from app.embeddings.service import EmbeddingService


def chunk_and_embed_documents(
    documents: Sequence[Document],
    embedding_service: EmbeddingService,
    *,
    strategy: str = "fixed",
    chunk_config: dict[str, Any] | None = None,
    semantic_embedding_model: Any = None,
) -> list[EmbeddedChunk]:
    """Chunk documents and embed them while preserving one-to-one mapping."""
    chunks = chunk_documents(
        list(documents),
        strategy=strategy,
        config=chunk_config,
        embedding_model=semantic_embedding_model,
    )
    return embedding_service.embed_chunks(chunks)
