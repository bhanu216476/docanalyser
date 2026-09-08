"""HTML document loading for the RAG service."""

from urllib.parse import urlparse

from app.config import configure_environment

configure_environment()

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document


def load_html(url: str) -> list[Document]:
    """Load an HTTP or HTTPS page as LangChain documents.

    Metadata supplied by ``WebBaseLoader``, including source and title when
    available, is returned unchanged.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty HTTP or HTTPS URL")

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("URL must be a valid HTTP or HTTPS URL")

    return WebBaseLoader(url).load()