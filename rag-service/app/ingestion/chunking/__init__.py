"""
Document chunking package for DocAnalyser RAG service.

Exports:
    - Chunk: Canonical immutable chunk data model.
    - BaseChunker: Abstract base class for all chunking algorithms.
    - FixedSizeChunker: Character-based fixed-size chunker with sliding window overlap.
    - RecursiveChunker: Recursive, structure-aware chunker with Markdown heading tracking.
"""

from app.ingestion.chunking.base import BaseChunker
from app.ingestion.chunking.fixed_size import (
    DEFAULT_FIXED_CHUNK_SIZE,
    DEFAULT_FIXED_OVERLAP,
    FixedSizeChunker,
)
from app.ingestion.chunking.models import Chunk
from app.ingestion.chunking.recursive import (
    DEFAULT_RECURSIVE_CHUNK_SIZE,
    DEFAULT_RECURSIVE_OVERLAP,
    RecursiveChunker,
)

__all__ = [
    "Chunk",
    "BaseChunker",
    "FixedSizeChunker",
    "RecursiveChunker",
    "DEFAULT_FIXED_CHUNK_SIZE",
    "DEFAULT_FIXED_OVERLAP",
    "DEFAULT_RECURSIVE_CHUNK_SIZE",
    "DEFAULT_RECURSIVE_OVERLAP",
]
