"""
Abstract base class for all document chunking strategies.

Defines the contract that every concrete chunker must satisfy.
Chunking implementations (FixedSizeChunker, RecursiveChunker, etc.)
must inherit from ``BaseChunker`` and implement ``chunk()``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence

from app.ingestion.chunking.models import Chunk
from app.ingestion.metadata_normalizer import compute_content_hash
from app.ingestion.models import Document

logger = logging.getLogger(__name__)


class BaseChunker(ABC):
    """
    Common abstraction for document chunking algorithms.

    Subclasses must implement:
        - ``chunk(document)``: Split a Document into a sequence of ordered Chunks.

    Provides common utilities for:
        - Deterministic document ID resolution
        - Deterministic chunk ID generation
        - Metadata inheritance and preservation
        - Batch document chunking
    """

    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        """
        Split a Document into an ordered list of non-empty Chunks.

        Args:
            document: Loaded Document instance.

        Returns:
            List of ordered Chunk instances. If document content is empty,
            returns an empty list.
        """
        ...  # pragma: no cover

    def chunk_documents(self, documents: Sequence[Document]) -> list[Chunk]:
        """
        Chunk a sequence of documents in order.

        Args:
            documents: Sequence of Document instances.

        Returns:
            Flattened list of all chunks produced across all documents.
        """
        all_chunks: list[Chunk] = []
        for doc in documents:
            all_chunks.extend(self.chunk(doc))
        return all_chunks

    @staticmethod
    def _resolve_document_id(document: Document) -> str:
        """
        Extract or deterministically derive a unique document ID.

        Checks:
            1. ``document.metadata["document_id"]``
            2. ``document.metadata["id"]``
            3. ``document.metadata["content_hash"]``
            4. Deterministic SHA-256 hash computed directly from ``document.content``

        Args:
            document: Source document.

        Returns:
            Deterministic string identifier for the source document.
        """
        meta_id = document.metadata.get("document_id") or document.metadata.get("id")
        if meta_id is not None:
            return str(meta_id)

        content_hash = document.metadata.get("content_hash")
        if content_hash is not None:
            return str(content_hash)

        return compute_content_hash(document.content)

    @staticmethod
    def _generate_chunk_id(document_id: str, chunk_index: int) -> str:
        """
        Generate a deterministic chunk ID from the document ID and chunk index.

        Format: ``{document_id}:{chunk_index}``

        Args:
            document_id: Source document identifier.
            chunk_index: 0-based sequential index of the chunk.

        Returns:
            Predictable, unique chunk ID string.
        """
        return f"{document_id}:{chunk_index}"

    @staticmethod
    def _build_chunk_metadata(
        document: Document,
        chunk_index: int,
        document_id: str,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Construct a comprehensive metadata dictionary for a generated chunk.

        Retains source provenance while incorporating chunking parameters.

        Args:
            document: Source document.
            chunk_index: 0-based chunk index.
            document_id: Resolved document identifier.
            extra_metadata: Strategy-specific or heading metadata.

        Returns:
            Merged metadata dictionary.
        """
        meta: dict[str, Any] = {
            "document_id": document_id,
            "source": document.source,
            "file_name": document.file_name,
            "file_type": document.file_type,
            "chunk_index": chunk_index,
        }

        # Inherit non-internal loader metadata (e.g. encoding)
        for key, value in document.metadata.items():
            if key not in meta and key not in ("content_hash", "size_bytes"):
                meta[key] = value

        if extra_metadata:
            meta.update(extra_metadata)

        return meta
