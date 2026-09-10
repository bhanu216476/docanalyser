"""Tests for recursive character chunking strategy."""

import pytest
from langchain_core.documents import Document
from app.chunking.recursive import recursive_chunk_documents


def test_recursive_chunking_basic():
    paragraphs = ["Paragraph " + str(i) + ". " + ("Word " * 20) for i in range(10)]
    text = "\n\n".join(paragraphs)
    doc = Document(page_content=text, metadata={"source": "test_rec.txt", "source_type": "pdf", "page_number": 1})

    chunks = recursive_chunk_documents([doc], chunk_size=300, chunk_overlap=30)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.page_content) <= 350
        assert chunk.metadata["chunking_strategy"] == "recursive"
        assert chunk.metadata["source"] == "test_rec.txt"
        assert chunk.metadata["page_number"] == 1


def test_recursive_chunking_invalid_params():
    doc = Document(page_content="Text", metadata={})
    with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
        recursive_chunk_documents([doc], chunk_size=-10)

    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        recursive_chunk_documents([doc], chunk_size=100, chunk_overlap=-1)

    with pytest.raises(ValueError, match="strictly less than chunk_size"):
        recursive_chunk_documents([doc], chunk_size=100, chunk_overlap=150)


def test_recursive_chunking_empty_doc():
    doc = Document(page_content="   ", metadata={})
    chunks = recursive_chunk_documents([doc])
    assert len(chunks) == 0


def test_recursive_chunking_custom_separators():
    text = "Section 1|Section 2|Section 3"
    doc = Document(page_content=text, metadata={"source": "pipe.txt"})
    chunks = recursive_chunk_documents([doc], chunk_size=12, chunk_overlap=0, separators=["|"])
    assert len(chunks) == 3
    assert "Section 1" in chunks[0].page_content
    assert "Section 2" in chunks[1].page_content
    assert "Section 3" in chunks[2].page_content
