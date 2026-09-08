from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from app.ingestion.html_loader import load_html


def test_load_html_returns_documents_and_preserves_metadata():
    expected = [
        Document(
            page_content="Deterministic HTML content",
            metadata={"source": "https://example.com/page", "title": "Example"},
        )
    ]

    with patch("app.ingestion.html_loader.WebBaseLoader") as loader_class:
        loader_class.return_value.load.return_value = expected

        documents = load_html("https://example.com/page")

    loader_class.assert_called_once_with("https://example.com/page")
    assert isinstance(documents, list)
    assert all(isinstance(document, Document) for document in documents)
    assert documents[0].page_content
    assert documents[0].metadata["source"] == "https://example.com/page"
    assert documents[0].metadata["title"] == "Example"


@pytest.mark.parametrize("url", ["example.com", "", "ftp://example.com"])
def test_load_html_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        load_html(url)