from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.ingestion.pdf_loader import load_pdf


def _pdf_fixture(path: Path) -> None:
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length 57 >>\nstream\nBT /F1 12 Tf 72 720 Td (IntelliResearch PDF Loader Test) Tj ET\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_offset = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    pdf += str(xref_offset).encode() + b"\n%%EOF\n"
    path.write_bytes(pdf)


def test_load_pdf_returns_page_documents(tmp_path):
    pdf_path = tmp_path / "fixture.pdf"
    _pdf_fixture(pdf_path)

    documents = load_pdf(str(pdf_path))

    assert isinstance(documents, list)
    assert documents
    assert all(isinstance(document, Document) for document in documents)
    assert documents[0].page_content.strip()
    assert documents[0].metadata
    assert documents[0].metadata["source"] == str(pdf_path)
    assert documents[0].metadata.get("page") == 0


def test_load_pdf_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_pdf("missing.pdf")


def test_load_pdf_rejects_non_pdf_file(tmp_path):
    text_path = tmp_path / "document.txt"
    text_path.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(ValueError):
        load_pdf(str(text_path))