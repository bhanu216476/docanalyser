"""PDF document loading for the RAG service."""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


from app.ingestion.processor import process_documents


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

    documents = PyPDFLoader(str(path)).load()
    for document in documents:
        document.metadata.setdefault("source", str(path))

    return process_documents(documents, source_type="pdf")
