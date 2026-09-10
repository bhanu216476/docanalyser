"""Tests for chunking service strategy dispatcher."""

import pytest
from langchain_core.documents import Document
from app.chunking.service import chunk_documents
from tests.chunking.fake_embeddings import FakeEmbeddings


def test_service_fixed_dispatch():
    doc = Document(page_content="A" * 500, metadata={"source": "test.txt"})
    chunks = chunk_documents([doc], strategy="fixed", config={"chunk_size": 200, "chunk_overlap": 20})
    assert len(chunks) == 3
    assert chunks[0].metadata["chunking_strategy"] == "fixed"


def test_service_recursive_dispatch():
    doc = Document(page_content="Para 1\n\nPara 2\n\nPara 3", metadata={"source": "test.txt"})
    chunks = chunk_documents([doc], strategy="recursive", config={"chunk_size": 10, "chunk_overlap": 0})
    assert len(chunks) == 3
    assert chunks[0].metadata["chunking_strategy"] == "recursive"


def test_service_semantic_dispatch():
    fake_emb = FakeEmbeddings()
    doc = Document(page_content="Introduction text. Method text.", metadata={"source": "test.txt"})
    chunks = chunk_documents([doc], strategy="semantic", embedding_model=fake_emb)
    assert len(chunks) >= 1
    assert chunks[0].metadata["chunking_strategy"] == "semantic"


def test_service_semantic_missing_model_error():
    doc = Document(page_content="Some text", metadata={})
    with pytest.raises(ValueError, match="requires an embedding_model"):
        chunk_documents([doc], strategy="semantic")


def test_service_invalid_strategy():
    doc = Document(page_content="Some text", metadata={})
    with pytest.raises(ValueError, match="Unsupported chunking strategy"):
        chunk_documents([doc], strategy="unknown_strategy")


def test_service_invalid_strategy_type():
    doc = Document(page_content="Some text", metadata={})
    with pytest.raises(ValueError, match="strategy must be one of"):
        chunk_documents([doc], strategy=None)
