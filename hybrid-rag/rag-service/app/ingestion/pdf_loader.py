"""PDF document loading for the RAG service."""

import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


from app.ingestion.processor import process_documents


def _max_pdf_size_bytes() -> int:
    return int(os.getenv("MAX_PDF_SIZE_BYTES", str(25 * 1024 * 1024)))


def load_pdf(file_path: str) -> list[Document]:
    """Load each page of a local PDF as a LangChain document.

    Loader-provided page metadata is retained, cleaned, and processed for future citations.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    if not path.is_file():
        raise FileNotFoundError(f"PDF path is not a file: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {file_path}")

    file_size = path.stat().st_size
    if file_size <= 0:
        raise ValueError(f"PDF file is empty: {file_path}")
    max_pdf_size_bytes = _max_pdf_size_bytes()
    if file_size > max_pdf_size_bytes:
        raise ValueError(
            f"PDF file is too large: {file_path} ({file_size} bytes exceeds {max_pdf_size_bytes} bytes)"
        )

    try:
        documents = PyPDFLoader(str(path)).load()
    except Exception as exc:  # pragma: no cover - defensive guard around parser failures
        raise ValueError(f"Failed to parse PDF file: {file_path}") from exc

    if not documents or not any(document.page_content.strip() for document in documents):
        raise ValueError(f"PDF file contains no extractable text: {file_path}")

    for document in documents:
        document.metadata.setdefault("source", str(path))

    return process_documents(documents, source_type="pdf")
