"""Tests for semantic chunking strategy with fake embeddings."""

import pytest
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from app.chunking.semantic import semantic_chunk_documents
from tests.chunking.fake_embeddings import FakeEmbeddings


class StubEmbeddings(Embeddings):
    def __init__(self, vectors):
        self.vectors = vectors

    def embed_documents(self, texts):
        return self.vectors

    def embed_query(self, text):
        return self.vectors[0]


def test_semantic_chunking_boundary_detection():
    fake_emb = FakeEmbeddings()
    text = (
        "Introduction to AI models. This section covers AI basics. "
        "Background details on machine learning. Deep learning architectures. "
        "Methodology description. Algorithm implementation details. "
        "Results show performance gains. Accuracy reached 98 percent. "
        "Conclusion summarizes findings. Future scope is discussed."
    )
    doc = Document(page_content=text, metadata={"source": "paper.pdf", "source_type": "pdf", "page_number": 1})

    chunks = semantic_chunk_documents(
        [doc],
        embedding_model=fake_emb,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=50.0
    )

    assert len(chunks) > 1
    assert fake_emb.embed_call_count > 0
    assert chunks[0].metadata["chunking_strategy"] == "semantic"
    assert chunks[0].metadata["source"] == "paper.pdf"
    assert chunks[0].metadata["page_number"] == 1


def test_semantic_chunking_missing_embeddings():
    doc = Document(page_content="Some content", metadata={})
    with pytest.raises(ValueError, match="embedding_model must be provided"):
        semantic_chunk_documents([doc], embedding_model=None)


@pytest.mark.parametrize("page_content", ["", "One sentence."])
def test_semantic_validates_threshold_type_before_early_returns(page_content):
    with pytest.raises(ValueError, match="Unsupported breakpoint_threshold_type"):
        semantic_chunk_documents(
            [Document(page_content=page_content, metadata={})],
            embedding_model=FakeEmbeddings(),
            breakpoint_threshold_type="invalid_type"
        )


def test_semantic_rejects_negative_buffer_size():
    with pytest.raises(ValueError, match="buffer_size must be non-negative"):
        semantic_chunk_documents(
            [Document(page_content="One. Two.", metadata={})],
            embedding_model=FakeEmbeddings(),
            buffer_size=-1
        )


@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ([[1.0, np.nan], [1.0, 2.0]], "only finite values"),
        ([[1.0, 2.0], [1.0]], "mismatched dimensions"),
    ]
)
def test_semantic_rejects_invalid_embedding_outputs(vectors, message):
    with pytest.raises(ValueError, match=message):
        semantic_chunk_documents(
            [Document(page_content="One. Two.", metadata={})],
            embedding_model=StubEmbeddings(vectors)
        )


def test_semantic_chunking_invalid_threshold_type():
    fake_emb = FakeEmbeddings()
    doc = Document(page_content="Sentence 1. Sentence 2.", metadata={})
    with pytest.raises(ValueError, match="Unsupported breakpoint_threshold_type"):
        semantic_chunk_documents(
            [doc],
            embedding_model=fake_emb,
            breakpoint_threshold_type="invalid_type"
        )


def test_semantic_chunking_deterministic():
    fake_emb = FakeEmbeddings()
    text = "Introduction topic text. Background topic text. Method topic text."
    doc = Document(page_content=text, metadata={"source": "det.pdf"})

    chunks1 = semantic_chunk_documents([doc], embedding_model=fake_emb, breakpoint_threshold_amount=50.0)
    chunks2 = semantic_chunk_documents([doc], embedding_model=fake_emb, breakpoint_threshold_amount=50.0)

    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.page_content == c2.page_content


def test_semantic_chunking_empty_and_single_sentence():
    fake_emb = FakeEmbeddings()
    empty_doc = Document(page_content="", metadata={})
    assert len(semantic_chunk_documents([empty_doc], embedding_model=fake_emb)) == 0

    single_doc = Document(page_content="Single sentence document.", metadata={"source": "s.txt"})
    single_chunks = semantic_chunk_documents([single_doc], embedding_model=fake_emb)
    assert len(single_chunks) == 1
    assert single_chunks[0].page_content == "Single sentence document."
