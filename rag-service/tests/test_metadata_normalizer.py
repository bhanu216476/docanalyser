"""
Unit tests for document metadata model and Python metadata normalization.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.ingestion import (
    Document,
    DocumentMetadata,
    DocumentStatus,
    MarkdownLoader,
    MetadataNormalizer,
    TxtLoader,
    compute_content_hash,
    infer_mime_type,
    normalize_file_type,
    normalize_source,
)


def test_txt_metadata_normalization():
    """Test 1 — TXT metadata: verify canonical output for a TXT document."""
    meta = MetadataNormalizer.normalize(
        file_name="notes.txt",
        content="Hello world\nDocAnalyser RAG.",
        source="/data/docs/notes.txt",
        file_type="txt",
        file_size=28,
    )

    assert isinstance(meta, DocumentMetadata)
    assert meta.file_name == "notes.txt"
    assert meta.file_type == "txt"
    assert meta.mime_type == "text/plain"
    assert meta.source == "/data/docs/notes.txt"
    assert meta.file_size == 28
    assert meta.status == DocumentStatus.PENDING
    assert len(meta.content_hash) == 64


def test_markdown_metadata_normalization():
    """Test 2 — Markdown metadata: verify canonical Markdown representation."""
    meta = MetadataNormalizer.normalize(
        file_name="README.md",
        content="# Overview\n\nDocAnalyser documentation.",
        source="/data/docs/README.md",
        file_type="markdown",
    )

    assert meta.file_name == "README.md"
    assert meta.file_type == "md"
    assert meta.mime_type == "text/markdown"
    assert meta.status == DocumentStatus.PENDING
    assert meta.file_size == len("# Overview\n\nDocAnalyser documentation.".encode("utf-8"))


def test_extension_normalization():
    """Test 3 — Extension normalization: verify extensions are mapped to canonical form."""
    assert normalize_file_type(".TXT") == "txt"
    assert normalize_file_type("txt") == "txt"
    assert normalize_file_type("TXT") == "txt"
    assert normalize_file_type(".md") == "md"
    assert normalize_file_type(".MD") == "md"
    assert normalize_file_type(".markdown") == "md"
    assert normalize_file_type("MARKDOWN") == "md"
    assert normalize_file_type(".pdf") == "pdf"
    assert normalize_file_type(".html") == "html"


def test_file_size_validation():
    """Test 4 — File size: verify byte representation and non-negative constraints."""
    meta = MetadataNormalizer.normalize(
        file_name="doc.txt",
        content="Sample content",
        source="/docs/doc.txt",
        file_size=1024,
    )
    assert meta.file_size == 1024

    with pytest.raises(ValueError, match="non-negative"):
        MetadataNormalizer.normalize(
            file_name="doc.txt",
            content="Sample",
            source="/docs/doc.txt",
            file_size=-5,
        )


def test_identical_content_produces_identical_hash():
    """Test 5 — Content hash: verify identical content produces identical SHA-256 hashes."""
    content1 = "Consistent content to verify deterministic hashing."
    content2 = "Consistent content to verify deterministic hashing."

    hash1 = compute_content_hash(content1)
    hash2 = compute_content_hash(content2)

    assert hash1 == hash2
    assert len(hash1) == 64

    # Verify through normalizer
    meta1 = MetadataNormalizer.normalize(
        file_name="file1.txt", content=content1, source="/path/1"
    )
    meta2 = MetadataNormalizer.normalize(
        file_name="file2.txt", content=content2, source="/path/2"
    )
    assert meta1.content_hash == meta2.content_hash


def test_different_content_produces_different_hashes():
    """Test 6 — Different content: verify different content produces different hashes."""
    hash1 = compute_content_hash("Document content variant A.")
    hash2 = compute_content_hash("Document content variant B.")

    assert hash1 != hash2


def test_invalid_metadata_rejected():
    """Test 7 — Invalid metadata: verify missing or invalid required values are rejected."""
    # Empty file_name rejected
    with pytest.raises(ValueError):
        MetadataNormalizer.normalize(
            file_name="",
            content="Valid content",
            source="/path/to/file",
        )

    # Empty source rejected
    with pytest.raises(ValueError):
        MetadataNormalizer.normalize(
            file_name="file.txt",
            content="Valid content",
            source="",
        )

    # Empty file_type rejected
    with pytest.raises(ValueError):
        normalize_file_type("")

    # Direct Pydantic validation on invalid hash length
    with pytest.raises(ValidationError):
        DocumentMetadata(
            file_name="doc.txt",
            file_type="txt",
            mime_type="text/plain",
            source="/path",
            file_size=10,
            content_hash="too_short",
        )


def test_status_handling():
    """Verify default status is PENDING and explicit status is preserved."""
    meta_default = MetadataNormalizer.normalize(
        file_name="test.txt",
        content="Testing status",
        source="/path/test.txt",
    )
    assert meta_default.status == DocumentStatus.PENDING

    meta_processed = MetadataNormalizer.normalize(
        file_name="test.txt",
        content="Testing status",
        source="/path/test.txt",
        status=DocumentStatus.PROCESSED,
    )
    assert meta_processed.status == DocumentStatus.PROCESSED


def test_loader_to_canonical_metadata_integration(tmp_path: Path):
    """Verify end-to-end integration: Loader -> Document -> Canonical DocumentMetadata."""
    # 1. TXT Loader
    txt_path = tmp_path / "sample.txt"
    txt_content = "Integration test for TXT loader and metadata normalization."
    txt_path.write_text(txt_content, encoding="utf-8")

    txt_doc = TxtLoader().load(txt_path)
    txt_meta = txt_doc.to_canonical_metadata()

    assert isinstance(txt_meta, DocumentMetadata)
    assert txt_meta.file_name == "sample.txt"
    assert txt_meta.file_type == "txt"
    assert txt_meta.mime_type == "text/plain"
    assert txt_meta.file_size == txt_path.stat().st_size
    assert txt_meta.content_hash == compute_content_hash(txt_doc.content)
    assert txt_meta.status == DocumentStatus.PENDING

    # 2. Markdown Loader
    md_path = tmp_path / "sample.markdown"
    md_content = "# Markdown Spec\n\n- Point 1\n- Point 2"
    md_path.write_text(md_content, encoding="utf-8")

    md_doc = MarkdownLoader().load(md_path)
    md_meta = MetadataNormalizer.from_document(md_doc)

    assert isinstance(md_meta, DocumentMetadata)
    assert md_meta.file_name == "sample.markdown"
    assert md_meta.file_type == "md"
    assert md_meta.mime_type == "text/markdown"
    assert md_meta.file_size == md_path.stat().st_size
    assert md_meta.content_hash == compute_content_hash(md_doc.content)
