"""Offline tests for chunk-to-vector mapping."""

import math

import pytest
from langchain_core.documents import Document

from app.chunking.service import chunk_documents
from app.embeddings import (
    EmbeddedChunk,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingService,
    EmbeddingValidationError,
    FakeEmbeddingProvider,
)
from app.embeddings.pipeline import chunk_and_embed_documents
from tests.chunking.fake_embeddings import FakeEmbeddings


class InvalidVectorProvider(EmbeddingProvider):
    def __init__(self, vectors):
        self.vectors = vectors

    def embed_batch(self, texts):
        return self.vectors


class AlternatingDimensionProvider(EmbeddingProvider):
    def __init__(self):
        self.calls = 0

    def embed_batch(self, texts):
        self.calls += 1
        dimension = 2 if self.calls == 1 else 3
        return [[float(index)] * dimension for index, _ in enumerate(texts)]


def _service(provider=None, batch_size=20):
    return EmbeddingService(
        provider=provider or FakeEmbeddingProvider(dimension=4),
        batch_size=batch_size,
        max_tokens=1000,
        sleep_fn=lambda _: None,
    )


def test_empty_chunks_return_empty_mapping():
    provider = FakeEmbeddingProvider(dimension=4)

    assert _service(provider).embed_chunks([]) == []
    assert provider.call_count == 0


def test_embedded_chunk_keeps_one_to_one_order_and_metadata():
    chunks = [
        Document(
            page_content=f"content {index}",
            metadata={
                "document_id": "doc-1",
                "chunk_id": f"doc-1_chunk_{index}",
                "chunk_index": index,
                "total_chunks": 2,
                "chunking_strategy": "fixed",
                "page_numbers": [index + 1],
                "page_number": index + 1,
                "headings": ["Heading"],
                "source_type": "pdf",
                "source": "doc.pdf",
            },
        )
        for index in range(2)
    ]

    embedded = _service().embed_chunks(chunks)

    assert len(embedded) == len(chunks) == 2
    assert all(isinstance(item, EmbeddedChunk) for item in embedded)
    assert [item.chunk_id for item in embedded] == [
        chunk.metadata["chunk_id"] for chunk in chunks
    ]
    assert [item.content for item in embedded] == [chunk.page_content for chunk in chunks]
    assert [item.index for item in embedded] == [0, 1]
    assert all(item.vector is item.embedding for item in embedded)
    assert embedded[0].metadata["page_number"] == 1
    assert embedded[0].metadata["document_id"] == "doc-1"
    assert embedded[0].metadata["chunk_index"] == 0
    assert embedded[0].metadata["total_chunks"] == 2
    assert embedded[0].metadata["chunking_strategy"] == "fixed"
    assert embedded[0].metadata["page_numbers"] == [1]
    assert embedded[0].metadata["headings"] == ["Heading"]
    assert embedded[0].metadata["source_type"] == "pdf"


def test_batch_embedding_preserves_order_and_count():
    provider = FakeEmbeddingProvider(dimension=4)
    chunks = [
        Document(
            page_content=f"content {index}",
            metadata={"chunk_id": f"chunk-{index}"},
        )
        for index in range(5)
    ]

    embedded = _service(provider, batch_size=2).embed_chunks(chunks)

    assert len(embedded) == 5
    assert provider.call_count == 3
    assert [item.chunk_id for item in embedded] == [f"chunk-{i}" for i in range(5)]
    assert len({len(item.vector) for item in embedded}) == 1


def test_duplicate_chunk_ids_are_rejected():
    chunks = [
        Document(page_content="one", metadata={"chunk_id": "duplicate"}),
        Document(page_content="two", metadata={"chunk_id": "duplicate"}),
    ]

    with pytest.raises(EmbeddingValidationError, match="Duplicate chunk_id"):
        _service().embed_chunks(chunks)


def test_dimensions_must_match_across_batches():
    provider = AlternatingDimensionProvider()
    chunks = [
        Document(
            page_content=f"content {index}",
            metadata={"chunk_id": f"chunk-{index}"},
        )
        for index in range(3)
    ]

    with pytest.raises(EmbeddingProviderError, match="across batches"):
        _service(provider, batch_size=2).embed_chunks(chunks)


@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ([[1.0, math.nan]], "NaN or infinity"),
        ([[1.0, math.inf]], "NaN or infinity"),
        ([[]], "non-empty"),
        ([[1.0, 2.0], [1.0]], "inconsistent dimensions"),
    ],
)
def test_invalid_vectors_are_rejected(vectors, message):
    provider = InvalidVectorProvider(vectors)
    chunks = [
        Document(
            page_content=f"content {index}",
            metadata={"chunk_id": f"chunk-{index}"},
        )
        for index in range(len(vectors))
    ]

    with pytest.raises(EmbeddingProviderError, match=message):
        _service(provider).embed_chunks(chunks)


@pytest.mark.parametrize("strategy", ["fixed", "recursive", "semantic"])
def test_all_chunking_strategies_feed_the_same_embedding_mapping(strategy):
    document = Document(
        page_content=(
            "Introduction topic. Introduction detail.\n\n"
            "Results topic. Results detail."
        ),
        metadata={
            "document_id": "doc-strategy",
            "source_type": "pdf",
            "page_number": 3,
            "page_numbers": [3],
            "headings": ["Introduction"],
        },
    )
    chunk_config = {"chunk_size": 100, "chunk_overlap": 0}
    if strategy == "semantic":
        chunk_config = {
            "breakpoint_threshold_type": "absolute",
            "breakpoint_threshold_amount": 0.5,
            "buffer_size": 0,
        }

    embedded = chunk_and_embed_documents(
        [document],
        _service(),
        strategy=strategy,
        chunk_config=chunk_config,
        semantic_embedding_model=FakeEmbeddings() if strategy == "semantic" else None,
    )

    assert embedded
    assert all(item.chunk_id for item in embedded)
    assert all(item.metadata["document_id"] == "doc-strategy" for item in embedded)
    assert all(item.metadata["page_number"] == 3 for item in embedded)
    assert all(item.metadata["headings"] == ["Introduction"] for item in embedded)
    assert len({len(item.vector) for item in embedded}) == 1


def test_semantic_chunking_embedding_stage_does_not_make_network_calls():
    document = Document(
        page_content="Introduction topic. Results topic.",
        metadata={"document_id": "offline", "chunk_id": "unused"},
    )

    embedded = chunk_and_embed_documents(
        [document],
        _service(),
        strategy="semantic",
        chunk_config={"breakpoint_threshold_type": "absolute", "breakpoint_threshold_amount": 0.5},
        semantic_embedding_model=FakeEmbeddings(),
    )

    assert embedded