"""
Unit tests for document loaders (TxtLoader, MarkdownLoader) and common loader interface.
"""

from pathlib import Path
import pytest

from app.ingestion import BaseLoader, Document, MarkdownLoader, TxtLoader


# ---------------------------------------------------------------------------
# TXT Loader Tests
# ---------------------------------------------------------------------------


def test_txt_loader_valid(tmp_path: Path):
    """Test 1 — Valid TXT: verify successful load, content, and metadata."""
    file_path = tmp_path / "sample.txt"
    content = "This is a sample document.\n\nIt contains multiple paragraphs."
    file_path.write_text(content, encoding="utf-8")

    loader = TxtLoader()
    doc = loader.load(file_path)

    assert isinstance(doc, Document)
    assert doc.content == content
    assert doc.file_name == "sample.txt"
    assert doc.file_type == "txt"
    assert doc.source == str(file_path.resolve())
    assert doc.metadata["encoding"] == "utf-8"
    assert doc.metadata["size_bytes"] == file_path.stat().st_size


def test_txt_loader_utf8(tmp_path: Path):
    """Test 2 — UTF-8 TXT: verify non-ASCII Unicode characters load accurately."""
    file_path = tmp_path / "unicode.txt"
    content = "DocAnalyser supports multilingual text: café, résumé, München, 日本語, 🚀."
    file_path.write_text(content, encoding="utf-8")

    loader = TxtLoader()
    doc = loader.load(file_path)

    assert doc.content == content


def test_txt_loader_empty(tmp_path: Path):
    """Test 3 — Empty TXT: verify explicit ValueError when file is empty or whitespace only."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    loader = TxtLoader()
    with pytest.raises(ValueError) as exc_info:
        loader.load(empty_file)
    assert "empty after loading" in str(exc_info.value)

    # Whitespace only file
    ws_file = tmp_path / "whitespace.txt"
    ws_file.write_text("   \n\n\t  \r\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info_ws:
        loader.load(ws_file)
    assert "empty after loading" in str(exc_info_ws.value)


def test_txt_loader_missing(tmp_path: Path):
    """Test 4 — Missing TXT: verify FileNotFoundError when file does not exist."""
    missing_file = tmp_path / "nonexistent.txt"

    loader = TxtLoader()
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load(missing_file)
    assert "File not found" in str(exc_info.value)


def test_txt_loader_unsupported_extension(tmp_path: Path):
    """Test 5 — Unsupported extension: verify rejection for non-txt files (e.g. .pdf)."""
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_text("dummy binary content", encoding="utf-8")

    loader = TxtLoader()
    with pytest.raises(ValueError) as exc_info:
        loader.load(pdf_file)
    assert "Unsupported file extension '.pdf'" in str(exc_info.value)


def test_txt_loader_cleaning_normalisation(tmp_path: Path):
    """Verify that CRLF line endings are normalised to LF and null bytes stripped."""
    file_path = tmp_path / "dirty.txt"
    raw_content = b"Line 1\r\nLine \x002\rLine 3\r\n"
    file_path.write_bytes(raw_content)

    loader = TxtLoader()
    doc = loader.load(file_path)

    assert doc.content == "Line 1\nLine 2\nLine 3"


def test_txt_loader_invalid_encoding(tmp_path: Path):
    """Verify that non-UTF-8 bytes trigger UnicodeDecodeError."""
    file_path = tmp_path / "bad_encoding.txt"
    # Write invalid UTF-8 bytes (e.g. Latin-1 0xE9 without UTF-8 header)
    file_path.write_bytes(b"Invalid bytes \xe9\x00\xff")

    loader = TxtLoader()
    with pytest.raises(UnicodeDecodeError):
        loader.load(file_path)


# ---------------------------------------------------------------------------
# Markdown Loader Tests
# ---------------------------------------------------------------------------


def test_markdown_loader_valid(tmp_path: Path):
    """Test 6 — Valid Markdown: verify successful loading and metadata."""
    file_path = tmp_path / "document.md"
    content = "# Document Title\n\nThis is a paragraph with **bold** text."
    file_path.write_text(content, encoding="utf-8")

    loader = MarkdownLoader()
    doc = loader.load(file_path)

    assert isinstance(doc, Document)
    assert doc.content == content
    assert doc.file_name == "document.md"
    assert doc.file_type == "md"
    assert doc.source == str(file_path.resolve())
    assert doc.metadata["encoding"] == "utf-8"
    assert doc.metadata["format"] == "markdown"


def test_markdown_loader_preserves_structure(tmp_path: Path):
    """Test 7 — Markdown structure: verify headings, lists, formatting are preserved (Option A)."""
    file_path = tmp_path / "guide.markdown"
    content = (
        "# Introduction\n\n"
        "This is **important** information.\n\n"
        "## Features\n"
        "- Item one\n"
        "- Item two\n\n"
        "```python\n"
        "def hello():\n"
        "    return 'world'\n"
        "```"
    )
    file_path.write_text(content, encoding="utf-8")

    loader = MarkdownLoader()
    doc = loader.load(file_path)

    assert doc.content == content
    assert doc.file_type == "markdown"
    assert "# Introduction" in doc.content
    assert "**important**" in doc.content
    assert "- Item one" in doc.content
    assert "```python" in doc.content


def test_markdown_loader_utf8(tmp_path: Path):
    """Test 8 — UTF-8 Markdown: verify multilingual and emoji characters."""
    file_path = tmp_path / "multilingual.md"
    content = "# Über uns 🌐\n\nDocAnalyser gère les documents en français et 中文."
    file_path.write_text(content, encoding="utf-8")

    loader = MarkdownLoader()
    doc = loader.load(file_path)

    assert doc.content == content


def test_markdown_loader_missing(tmp_path: Path):
    """Test 9 — Missing Markdown: verify FileNotFoundError when file does not exist."""
    missing_file = tmp_path / "missing.md"

    loader = MarkdownLoader()
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load(missing_file)
    assert "File not found" in str(exc_info.value)


def test_markdown_loader_unsupported_extension(tmp_path: Path):
    """Test 10 — Unsupported extension: verify rejection for unsupported formats (e.g. .docx)."""
    docx_file = tmp_path / "notes.docx"
    docx_file.write_text("sample content", encoding="utf-8")

    loader = MarkdownLoader()
    with pytest.raises(ValueError) as exc_info:
        loader.load(docx_file)
    assert "Unsupported file extension '.docx'" in str(exc_info.value)


def test_markdown_loader_empty(tmp_path: Path):
    """Verify rejection when markdown file is empty or only whitespace."""
    empty_file = tmp_path / "empty.md"
    empty_file.write_text("   \n\t ", encoding="utf-8")

    loader = MarkdownLoader()
    with pytest.raises(ValueError) as exc_info:
        loader.load(empty_file)
    assert "empty after loading" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Common Interface Tests
# ---------------------------------------------------------------------------


def test_common_loader_interface(tmp_path: Path):
    """
    Test 11 — Common interface: verify that both TxtLoader and MarkdownLoader
    conform to BaseLoader and can be executed via a uniform interface.
    """
    txt_file = tmp_path / "file.txt"
    txt_file.write_text("Plain text content", encoding="utf-8")

    md_file = tmp_path / "file.md"
    md_file.write_text("# Markdown content", encoding="utf-8")

    loaders: list[tuple[BaseLoader, Path]] = [
        (TxtLoader(), txt_file),
        (MarkdownLoader(), md_file),
    ]

    for loader, path in loaders:
        assert isinstance(loader, BaseLoader)
        doc = loader.load(path)
        assert isinstance(doc, Document)
        assert doc.source == str(path.resolve())
        assert len(doc.content) > 0


def test_fixture_files_load():
    """Verify that fixture files in tests/fixtures load without errors."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    sample_txt = fixtures_dir / "sample.txt"
    sample_md = fixtures_dir / "sample.md"

    txt_doc = TxtLoader().load(sample_txt)
    assert txt_doc.file_name == "sample.txt"
    assert "DocAnalyser Ingestion Pipeline" in txt_doc.content

    md_doc = MarkdownLoader().load(sample_md)
    assert md_doc.file_name == "sample.md"
    assert "# Sample Markdown Document" in md_doc.content

