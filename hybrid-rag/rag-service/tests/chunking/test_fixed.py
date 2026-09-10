"""Tests for fixed-size chunking strategy."""

import pytest
from langchain_core.documents import Document
from app.chunking.fixed import fixed_chunk_documents


def test_fixed_chunking_basic():
    text = "A" * 2500
    doc = Document(page_content=text, metadata={"source": "test.txt", "source_type": "pdf", "page_number": 1})
    chunks = fixed_chunk_documents([doc], chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 3
    assert chunks[0].page_content == "A" * 1000
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["chunking_strategy"] == "fixed"
    assert chunks[0].metadata["source"] == "test.txt"
    assert chunks[0].metadata["page_number"] == 1


def test_fixed_chunking_overlap():
    text = "0123456789" * 10  # 100 characters
    doc = Document(page_content=text, metadata={"source": "numbers.txt"})
    chunks = fixed_chunk_documents([doc], chunk_size=50, chunk_overlap=10)

    assert len(chunks) > 1
    # End of chunk 0 should overlap start of chunk 1
    chunk0_end = chunks[0].page_content[-10:]
    chunk1_start = chunks[1].page_content[:10]
    assert chunk0_end == chunk1_start


def test_fixed_chunking_invalid_params():
    doc = Document(page_content="Hello world", metadata={})

    with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
        fixed_chunk_documents([doc], chunk_size=0)

    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        fixed_chunk_documents([doc], chunk_size=100, chunk_overlap=-5)

    with pytest.raises(ValueError, match="strictly less than chunk_size"):
        fixed_chunk_documents([doc], chunk_size=100, chunk_overlap=100)


def test_fixed_chunking_empty_doc():
    doc = Document(page_content="", metadata={"source": "empty.txt"})
    chunks = fixed_chunk_documents([doc])
    assert len(chunks) == 0


def test_fixed_chunking_short_doc():
    doc = Document(page_content="Short text", metadata={"source": "short.txt"})
    chunks = fixed_chunk_documents([doc], chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0].page_content == "Short text"
    assert chunks[0].metadata["total_chunks"] == 1
