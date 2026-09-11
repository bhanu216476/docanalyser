from langchain_core.documents import Document

from app.ingestion.processor import process_documents


def test_process_pdf_documents_page_tracking_and_metadata():
    raw_docs = [
        Document(
            page_content="   # Chapter 1   \n\n   Example page 1 content   \n\n\n",
            metadata={"source": "sample.pdf", "page": 0},
        ),
        Document(
            page_content="   # Chapter 2   \n\n   Example page 2 content   ",
            metadata={"source": "sample.pdf", "page": 1},
        ),
    ]

    processed = process_documents(raw_docs, source_type="pdf")

    assert len(processed) == 2
    assert all(isinstance(doc, Document) for doc in processed)

    # First doc assertion
    assert processed[0].page_content == "# Chapter 1\n\nExample page 1 content"
    assert processed[0].metadata["source"] == "sample.pdf"
    assert processed[0].metadata["page"] == 0
    assert processed[0].metadata["page_number"] == 1
    assert processed[0].metadata["source_type"] == "pdf"
    assert processed[0].metadata["headings"] == ["Chapter 1"]

    # Second doc assertion
    assert processed[1].metadata["page"] == 1
    assert processed[1].metadata["page_number"] == 2
    assert processed[1].metadata["source_type"] == "pdf"
    assert processed[1].metadata["headings"] == ["Chapter 2"]


def test_process_html_documents_metadata_and_no_page_number():
    raw_docs = [
        Document(
            page_content="   <h1>Title</h1>\n\n   HTML page content   ",
            metadata={"source": "https://example.com", "title": "Example Page"},
        )
    ]

    processed = process_documents(raw_docs, source_type="html")

    assert len(processed) == 1
    doc = processed[0]
    assert isinstance(doc, Document)
    assert doc.metadata["source"] == "https://example.com"
    assert doc.metadata["title"] == "Example Page"
    assert doc.metadata["source_type"] == "html"
    assert "page_number" not in doc.metadata
    assert isinstance(doc.metadata["headings"], list)
