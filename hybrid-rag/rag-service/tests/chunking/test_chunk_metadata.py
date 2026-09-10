"""Tests for metadata preservation during chunking."""

from langchain_core.documents import Document
from app.chunking.fixed import fixed_chunk_documents
from app.chunking.models import Chunk, build_chunk_document


def test_metadata_preservation_fields():
    doc = Document(
        page_content="Header line\nParagraph text line one.\nParagraph text line two.",
        metadata={
            "source": "doc1.pdf",
            "source_type": "pdf",
            "page": 0,
            "page_number": 1,
            "headings": ["Header line"],
            "custom_attribute": "custom_value"
        }
    )

    chunks = fixed_chunk_documents([doc], chunk_size=30, chunk_overlap=5)
    assert len(chunks) > 1

    for chunk in chunks:
        meta = chunk.metadata
        assert meta["source"] == "doc1.pdf"
        assert meta["source_type"] == "pdf"
        assert meta["page"] == 0
        assert meta["page_number"] == 1
        assert meta["headings"] == ["Header line"]
        assert meta["custom_attribute"] == "custom_value"
        assert "chunk_id" in meta
        assert "chunk_index" in meta
        assert "chunking_strategy" in meta


def test_chunk_pydantic_model_conversion():
    chunk_model = Chunk(
        chunk_id="doc1_chunk_0",
        content="Sample chunk content text",
        chunk_index=0,
        chunking_strategy="fixed",
        total_chunks=5,
        source="sample.pdf",
        source_type="pdf",
        document_id="doc1",
        page=0,
        page_number=1,
        page_numbers=[1, 2],
        headings=["Introduction"],
        metadata={"author": "Researcher"}
    )

    doc = chunk_model.to_document()
    assert doc.page_content == "Sample chunk content text"
    assert doc.metadata["chunk_id"] == "doc1_chunk_0"
    assert doc.metadata["source"] == "sample.pdf"
    assert doc.metadata["page_number"] == 1
    assert doc.metadata["page_numbers"] == [1, 2]
    assert doc.metadata["author"] == "Researcher"


def test_chunk_model_normalizes_page_numbers_and_representative_page():
    chunk_model = Chunk(
        chunk_id="doc1_chunk_0",
        content="Sample chunk content text",
        chunk_index=0,
        chunking_strategy="fixed",
        page=98,
        page_number=99,
        page_numbers=[5, 3, 3, 5, 7],
        metadata={"custom": "value"}
    )

    doc = chunk_model.to_document()

    assert doc.metadata["page_numbers"] == [5, 3, 7]
    assert doc.metadata["page_number"] == 5
    assert doc.metadata["page"] == 4
    assert doc.metadata["custom"] == "value"


def test_build_chunk_document_page_spanning():
    orig_doc = Document(
        page_content="Long content across pages",
        metadata={
            "source": "multi.pdf",
            "source_type": "pdf",
            "headings": ["Section 1"],
            "page": 98,
            "page_number": 99
        }
    )

    chunk_doc = build_chunk_document(
        content="Long content across pages",
        orig_doc=orig_doc,
        chunk_index=0,
        strategy="fixed",
        spanned_page_numbers=[5, 3, 3, 5, 7]
    )

    assert chunk_doc.metadata["page_numbers"] == [5, 3, 7]
    assert chunk_doc.metadata["page_number"] == 5
    assert chunk_doc.metadata["page"] == 4
    assert chunk_doc.metadata["source"] == "multi.pdf"


def test_empty_page_numbers_are_preserved():
    orig_doc = Document(
        page_content="Content",
        metadata={"source": "empty-pages.pdf", "page_number": 1}
    )

    chunk_doc = build_chunk_document(
        content="Content",
        orig_doc=orig_doc,
        chunk_index=0,
        strategy="fixed",
        spanned_page_numbers=[]
    )

    assert chunk_doc.metadata["page_numbers"] == []
    assert chunk_doc.metadata["page_number"] == 1


def test_parent_chunk_identity_is_unique_across_page_documents():
    documents = [
        Document(page_content="A" * 120, metadata={"document_id": "doc1", "page_number": 1}),
        Document(page_content="B" * 120, metadata={"document_id": "doc1", "page_number": 2}),
    ]

    chunks = fixed_chunk_documents(documents, chunk_size=100, chunk_overlap=0)

    assert len({chunk.metadata["chunk_id"] for chunk in chunks}) == len(chunks)
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1, 2, 3]
    assert {chunk.metadata["total_chunks"] for chunk in chunks} == {4}
