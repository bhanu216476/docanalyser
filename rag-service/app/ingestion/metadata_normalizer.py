"""
Metadata normalization module for DocAnalyser ingestion pipeline.

Ensures metadata produced across different loaders (TXT, Markdown, etc.)
is transformed into a canonical, deterministic format matching the persistence schema.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

from app.ingestion.metadata import DocumentMetadata, DocumentStatus
from app.ingestion.models import Document

# Canonical file extension mappings
_EXTENSION_MAP: dict[str, str] = {
    "txt": "txt",
    "text": "txt",
    "md": "md",
    "markdown": "md",
    "pdf": "pdf",
    "html": "html",
    "htm": "html",
}

# Standard IANA MIME types for supported file extensions
_MIME_MAP: dict[str, str] = {
    "txt": "text/plain",
    "md": "text/markdown",
    "pdf": "application/pdf",
    "html": "text/html",
}


def compute_content_hash(content: Union[str, bytes]) -> str:
    """
    Compute deterministic SHA-256 hexadecimal digest from document content.

    Args:
        content: Raw text content (string) or raw bytes.

    Returns:
        64-character lowercase SHA-256 hexadecimal string.
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    elif isinstance(content, bytes):
        content_bytes = content
    else:
        raise TypeError(f"Content must be str or bytes, got {type(content).__name__}")

    return hashlib.sha256(content_bytes).hexdigest()


def normalize_file_type(raw_file_type: str) -> str:
    """
    Normalize raw file extension or type identifier to canonical lowercase form.

    Examples:
        - ``.TXT`` -> ``txt``
        - ``.markdown`` -> ``md``
        - ``MD`` -> ``md``

    Args:
        raw_file_type: Raw extension string or type.

    Returns:
        Canonical extension without leading dot.

    Raises:
        ValueError: If raw_file_type is empty or invalid.
    """
    if not raw_file_type or not raw_file_type.strip():
        raise ValueError("File type cannot be empty")

    cleaned = raw_file_type.strip().lstrip(".").lower()
    if not cleaned:
        raise ValueError("File type cannot be empty after stripping dots")

    return _EXTENSION_MAP.get(cleaned, cleaned)


def infer_mime_type(file_type: str, fallback: str = "application/octet-stream") -> str:
    """
    Infer canonical IANA MIME type for a normalized file type.

    Args:
        file_type: Normalized file type (e.g. ``txt``, ``md``).
        fallback: MIME type to return if unrecognized.

    Returns:
        Canonical MIME type string.
    """
    canonical_type = normalize_file_type(file_type) if file_type else ""
    return _MIME_MAP.get(canonical_type, fallback)


def normalize_source(source: Union[str, Path]) -> str:
    """
    Normalize file source location into a consistent path representation.

    Replaces platform-specific backslashes with standard forward slashes.

    Args:
        source: File path or URI as string or Path.

    Returns:
        Clean normalized path string.

    Raises:
        ValueError: If source is empty.
    """
    if isinstance(source, Path):
        return source.as_posix()

    if not isinstance(source, str) or not source.strip():
        raise ValueError("Source path cannot be empty")

    # Normalize backslashes to forward slashes for cross-platform consistency
    cleaned = source.strip().replace("\\", "/")
    return cleaned


class MetadataNormalizer:
    """
    Service responsible for converting loader outputs and raw metadata
    into canonical ``DocumentMetadata``.
    """

    @classmethod
    def normalize(
        cls,
        *,
        file_name: str,
        content: str,
        source: Union[str, Path],
        file_type: Optional[str] = None,
        mime_type: Optional[str] = None,
        file_size: Optional[int] = None,
        content_hash: Optional[str] = None,
        status: DocumentStatus = DocumentStatus.PENDING,
        document_id: Optional[UUID] = None,
    ) -> DocumentMetadata:
        """
        Normalize and construct a canonical ``DocumentMetadata`` instance.

        Args:
            file_name: Basename of the file.
            content: Raw document text content (used for hash and default size).
            source: Source location or path.
            file_type: Raw or normalized file type (inferred from file_name if omitted).
            mime_type: Explicit MIME type (inferred from file_type if omitted).
            file_size: Size in bytes (inferred from content UTF-8 byte length if omitted).
            content_hash: Explicit SHA-256 hash (computed from content if omitted).
            status: Ingestion status enum.
            document_id: Optional UUID.

        Returns:
            Validated, immutable ``DocumentMetadata``.
        """
        if not file_name or not file_name.strip():
            raise ValueError("file_name cannot be empty")

        clean_file_name = file_name.strip()

        # Determine and normalize file_type
        if file_type is None:
            suffix = Path(clean_file_name).suffix
            if not suffix:
                raise ValueError(
                    f"Cannot infer file_type: file_name '{clean_file_name}' has no extension"
                )
            canon_file_type = normalize_file_type(suffix)
        else:
            canon_file_type = normalize_file_type(file_type)

        # Determine MIME type
        canon_mime_type = mime_type if mime_type else infer_mime_type(canon_file_type)

        # Normalize source
        canon_source = normalize_source(source)

        # File size: validate or infer
        if file_size is not None:
            if file_size < 0:
                raise ValueError("file_size must be a non-negative integer")
            canon_file_size = file_size
        else:
            canon_file_size = len(content.encode("utf-8"))

        # Content hash
        canon_hash = content_hash if content_hash else compute_content_hash(content)

        return DocumentMetadata(
            id=document_id,
            file_name=clean_file_name,
            file_type=canon_file_type,
            mime_type=canon_mime_type,
            source=canon_source,
            file_size=canon_file_size,
            content_hash=canon_hash,
            status=status,
        )

    @classmethod
    def from_document(
        cls,
        doc: Document,
        *,
        status: DocumentStatus = DocumentStatus.PENDING,
    ) -> DocumentMetadata:
        """
        Build a canonical ``DocumentMetadata`` from an existing loaded ``Document``.

        Args:
            doc: Loaded ``Document`` instance from any loader.
            status: Ingestion lifecycle status.

        Returns:
            Canonical ``DocumentMetadata``.
        """
        # Read file_size from doc.metadata if available, else infer from content
        size_bytes = doc.metadata.get("size_bytes")
        if size_bytes is not None and not isinstance(size_bytes, int):
            try:
                size_bytes = int(size_bytes)
            except (ValueError, TypeError):
                size_bytes = None

        return cls.normalize(
            file_name=doc.file_name,
            content=doc.content,
            source=doc.source,
            file_type=doc.file_type,
            file_size=size_bytes,
            status=status,
        )
