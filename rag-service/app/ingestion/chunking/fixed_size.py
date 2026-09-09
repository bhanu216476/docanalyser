"""
Fixed-size document chunker.

Splits documents into fixed-size windows measured in characters with
configurable character overlap.

Unit of measurement: Characters
    - Deterministic and fast with standard Python string slicing.
    - Zero external dependencies (no tokenizers required).
    - Platform-independent boundary calculations.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.ingestion.chunking.base import BaseChunker
from app.ingestion.chunking.models import Chunk
from app.ingestion.models import Document

logger = logging.getLogger(__name__)

DEFAULT_FIXED_CHUNK_SIZE: int = 1000
DEFAULT_FIXED_OVERLAP: int = 200


class FixedSizeChunker(BaseChunker):
    """
    Splits document content into chunks of fixed character length with overlap.

    Progression:
        - Chunk 0: content[0 : chunk_size]
        - Chunk 1: content[chunk_size - overlap : 2 * chunk_size - overlap]
        - ...

    Args:
        chunk_size: Maximum character length of each chunk. Must be > 0.
        overlap: Character overlap between consecutive chunks. Must be >= 0 and < chunk_size.

    Raises:
        ValueError: If chunk_size <= 0, overlap < 0, or overlap >= chunk_size.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_FIXED_CHUNK_SIZE,
        overlap: int = DEFAULT_FIXED_OVERLAP,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")
        if overlap < 0:
            raise ValueError(f"overlap must be a non-negative integer, got {overlap}")
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.step = chunk_size - overlap

    def chunk(self, document: Document) -> list[Chunk]:
        """
        Split a Document into ordered, fixed-size Chunks.

        Args:
            document: Loaded Document instance.

        Returns:
            List of ordered Chunk instances. If document is empty or whitespace only,
            returns an empty list.
        """
        text = document.content
        if not text or not text.strip():
            logger.debug(
                "FixedSizeChunker: Document '%s' is empty or whitespace-only, returning 0 chunks.",
                document.file_name,
            )
            return []

        doc_id = self._resolve_document_id(document)
        text_len = len(text)

        # Document smaller than or equal to chunk_size: return exactly one chunk
        if text_len <= self.chunk_size:
            meta = self._build_chunk_metadata(
                document,
                chunk_index=0,
                document_id=doc_id,
                extra_metadata={
                    "chunk_size": self.chunk_size,
                    "overlap": self.overlap,
                    "strategy": "fixed_size",
                },
            )
            return [
                Chunk(
                    chunk_id=self._generate_chunk_id(doc_id, 0),
                    document_id=doc_id,
                    content=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=text_len,
                    metadata=meta,
                )
            ]

        # Document larger than chunk_size: sliding window progression
        chunks: list[Chunk] = []
        start = 0
        chunk_index = 0

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_content = text[start:end]

            # Only emit non-empty chunks
            if chunk_content and chunk_content.strip():
                meta = self._build_chunk_metadata(
                    document,
                    chunk_index=chunk_index,
                    document_id=doc_id,
                    extra_metadata={
                        "chunk_size": self.chunk_size,
                        "overlap": self.overlap,
                        "strategy": "fixed_size",
                    },
                )
                chunks.append(
                    Chunk(
                        chunk_id=self._generate_chunk_id(doc_id, chunk_index),
                        document_id=doc_id,
                        content=chunk_content,
                        chunk_index=chunk_index,
                        start_char=start,
                        end_char=end,
                        metadata=meta,
                    )
                )
                chunk_index += 1

            if end >= text_len:
                break

            start += self.step

        logger.debug(
            "FixedSizeChunker: generated %d chunks for document '%s' (len=%d)",
            len(chunks),
            document.file_name,
            text_len,
        )
        return chunks
