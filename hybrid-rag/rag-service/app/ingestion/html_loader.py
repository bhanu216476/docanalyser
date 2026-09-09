"""HTML document loading for the RAG service."""

from urllib.parse import urlparse

from app.config import configure_environment

configure_environment()

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document


from app.ingestion.processor import process_documents


def load_html(url: str) -> list[Document]:
    """Load an HTTP or HTTPS page as LangChain documents.

    Metadata supplied by ``WebBaseLoader``, including source and title when
    available, is preserved and enhanced with source_type and headings.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty HTTP or HTTPS URL")

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("URL must be a valid HTTP or HTTPS URL")

    documents = WebBaseLoader(url).load()
    return process_documents(documents, source_type="html")
