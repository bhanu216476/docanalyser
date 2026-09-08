"""
Ingestion module for document loading, parsing, and preparation.

Exports:
    - Document: Common representation for loaded documents.
    - BaseLoader: Abstract base class for all file loaders.
    - TxtLoader: Plain text loader.
    - MarkdownLoader: Markdown file loader.
    - DocumentMetadata: Canonical metadata model.
    - DocumentStatus: Document lifecycle status enum.
    - MetadataNormalizer: Metadata normalization service.
    - compute_content_hash: Deterministic SHA-256 hash function.
    - normalize_file_type: Canonical file extension normalizer.
    - infer_mime_type: MIME type resolver.
    - normalize_source: Cross-platform source path normalizer.
"""

from app.ingestion.base import BaseLoader
from app.ingestion.markdown_loader import MarkdownLoader
from app.ingestion.metadata import DocumentMetadata, DocumentStatus
from app.ingestion.metadata_normalizer import (
    MetadataNormalizer,
    compute_content_hash,
    infer_mime_type,
    normalize_file_type,
    normalize_source,
)
from app.ingestion.models import Document
from app.ingestion.txt_loader import TxtLoader

__all__ = [
    "Document",
    "BaseLoader",
    "TxtLoader",
    "MarkdownLoader",
    "DocumentMetadata",
    "DocumentStatus",
    "MetadataNormalizer",
    "compute_content_hash",
    "normalize_file_type",
    "infer_mime_type",
    "normalize_source",
]
