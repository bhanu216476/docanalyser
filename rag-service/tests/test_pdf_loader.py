"""
Unit tests for PDFLoader.

Tests:
    - Valid single-page PDF extraction.
    - Valid multi-page PDF extraction.
    - Non-existent file raises FileNotFoundError.
    - Unsupported file extension raises ValueError.
    - Corrupt or invalid PDF structure raises ValueError.
    - Empty PDF (no extractable text) raises ValueError.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.ingestion.models import Document
from app.ingestion.pdf_loader import PDFLoader


def _generate_pdf(path: Path, pages: list[str]) -> None:
    """Generate a minimal valid PDF-1.4 binary file containing the given page texts."""
    objects: list[bytes] = []

    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Object 2: Pages container
    kids_refs = [f"{3 + i * 2} 0 R" for i in range(len(pages))]
    kids_str = " ".join(kids_refs)
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {len(pages)} >>\nendobj\n".encode("latin-1")
    )

    # Font object ID will be after all page and content objects
    font_id = 3 + len(pages) * 2

    # For each page: Page object + Contents stream object
    for idx, page_text in enumerate(pages):
        page_obj_id = 3 + idx * 2
        content_obj_id = page_obj_id + 1

        # Safe latin-1 escaped text stream
        escaped_text = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("latin-1")

        page_obj = (
            f"{page_obj_id} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_obj_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>\n"
            f"endobj\n"
        ).encode("latin-1")
        objects.append(page_obj)

        content_obj = (
            f"{content_obj_id} 0 obj\n"
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream\nendobj\n"
        )
        objects.append(content_obj)

    # Font object
    objects.append(
        f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("latin-1")
    )

    # Assemble complete PDF with xref table
    total_objects = len(objects) + 1  # include 0-th object
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_offset = len(pdf)
    pdf += f"xref\n0 {total_objects}\n0000000000 65535 f \n".encode("latin-1")
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("latin-1")

    pdf += (
        f"trailer\n<< /Size {total_objects} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")

    path.write_bytes(pdf)


def test_pdf_loader_valid_single_page(tmp_path: Path):
    pdf_path = tmp_path / "policy.pdf"
    _generate_pdf(pdf_path, ["Employees receive 12 casual leave days."])

    loader = PDFLoader()
    doc = loader.load(pdf_path)

    assert isinstance(doc, Document)
    assert "Employees receive 12 casual leave days." in doc.content
    assert doc.file_name == "policy.pdf"
    assert doc.file_type == "pdf"
    assert doc.source == str(pdf_path.resolve())
    assert doc.metadata["page_count"] == 1
    assert doc.metadata["size_bytes"] == pdf_path.stat().st_size
    assert len(doc.metadata["pages"]) == 1
    assert doc.metadata["pages"][0]["page_number"] == 1


def test_pdf_loader_multi_page(tmp_path: Path):
    pdf_path = tmp_path / "multi_policy.pdf"
    _generate_pdf(
        pdf_path,
        [
            "Chapter 1: Casual Leave Policy. Employees get 12 days.",
            "Chapter 2: Sick Leave Policy. Employees get 15 days.",
        ],
    )

    loader = PDFLoader()
    doc = loader.load(pdf_path)

    assert doc.metadata["page_count"] == 2
    assert "Chapter 1: Casual Leave Policy" in doc.content
    assert "Chapter 2: Sick Leave Policy" in doc.content
    assert len(doc.metadata["pages"]) == 2
    assert doc.metadata["pages"][0]["page_number"] == 1
    assert doc.metadata["pages"][1]["page_number"] == 2


def test_pdf_loader_nonexistent_file():
    loader = PDFLoader()
    with pytest.raises(FileNotFoundError):
        loader.load(Path("non_existent_file.pdf"))


def test_pdf_loader_unsupported_extension(tmp_path: Path):
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("Hello world", encoding="utf-8")

    loader = PDFLoader()
    with pytest.raises(ValueError) as exc:
        loader.load(txt_path)
    assert "Unsupported file extension" in str(exc.value)


def test_pdf_loader_corrupted_file(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"This is not a PDF at all.")

    loader = PDFLoader()
    with pytest.raises(ValueError) as exc:
        loader.load(corrupt_path)
    assert "Failed to read or parse PDF file" in str(exc.value)


def test_pdf_loader_empty_content(tmp_path: Path):
    empty_pdf = tmp_path / "empty.pdf"
    # Generate a PDF with whitespace-only content
    _generate_pdf(empty_pdf, ["   "])

    loader = PDFLoader()
    with pytest.raises(ValueError) as exc:
        loader.load(empty_pdf)
    assert "empty after loading" in str(exc.value)
