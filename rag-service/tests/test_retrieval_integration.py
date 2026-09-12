"""
Integration tests for DenseRetriever against in-memory Qdrant.

Uses qdrant-client's :memory: mode — no Docker or external service required.
Tests the complete retrieval pipeline end-to-end:

    Insert known vectors → generate query vector → dense search
        → verify top-K results → verify scores → verify metadata filters

These tests are marked @pytest.mark.integration for selective exclusion
from fast unit test runs, but they require NO external network access.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from app.embeddings.providers import FakeEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.ingestion.chunking.models import Chunk
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.models import RetrievalFilter, RetrievalResult
from app.vector_store.models import build_payload_from_chunk, generate_point_id
from app.vector_store.qdrant_store import QdrantVectorStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INTEG_COLLECTION = "dense_retrieval_integration_test"
INTEG_DIM = 8


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def memory_client() -> QdrantClient:
    """Single in-memory Qdrant client shared across all integration tests."""
    return QdrantClient(":memory:")


@pytest.fixture(scope="module")
def fake_provider() -> FakeEmbeddingProvider:
    """Shared FakeEmbeddingProvider configured with INTEG_DIM dimensions."""
    return FakeEmbeddingProvider(dimension=INTEG_DIM)


@pytest.fixture(scope="module")
def embedding_service(fake_provider: FakeEmbeddingProvider) -> EmbeddingService:
    """EmbeddingService wrapping the fake provider."""
    return EmbeddingService(
        provider=fake_provider,
        batch_size=10,
        max_tokens=8191,
        max_retries=0,
        sleep_fn=lambda _: None,
    )


@pytest.fixture(scope="module")
def populated_store(
    memory_client: QdrantClient,
    embedding_service: EmbeddingService,
) -> QdrantVectorStore:
    """
    Create an in-memory collection and insert 5 known chunks.

    The FakeEmbeddingProvider generates deterministic vectors from chunk content,
    so retrieval results are reproducible without real embedding models.
    """
    store = QdrantVectorStore(
        client=memory_client,
        collection_name=INTEG_COLLECTION,
        vector_size=INTEG_DIM,
        distance="Cosine",
    )
    store.ensure_collection()

    chunks = [
        Chunk(
            chunk_id=f"doc-hr:0",
            document_id="doc-hr",
            chunk_index=0,
            content="Annual leave entitlement is 20 days per year.",
            metadata={
                "file_name": "hr_policy.md",
                "file_type": "md",
                "source": "docs/hr_policy.md",
                "section": "Leave Policy",
            },
        ),
        Chunk(
            chunk_id="doc-hr:1",
            document_id="doc-hr",
            chunk_index=1,
            content="Casual leave is limited to 10 days per year.",
            metadata={
                "file_name": "hr_policy.md",
                "file_type": "md",
                "source": "docs/hr_policy.md",
                "section": "Leave Policy",
            },
        ),
        Chunk(
            chunk_id="doc-hr:2",
            document_id="doc-hr",
            chunk_index=2,
            content="Sick leave allowance is 12 days per year with medical certificate.",
            metadata={
                "file_name": "hr_policy.md",
                "file_type": "md",
                "source": "docs/hr_policy.md",
                "section": "Leave Policy",
            },
        ),
        Chunk(
            chunk_id="doc-tech:0",
            document_id="doc-tech",
            chunk_index=0,
            content="The system architecture uses a microservices pattern.",
            metadata={
                "file_name": "architecture.txt",
                "file_type": "txt",
                "source": "docs/architecture.txt",
                "section": "Overview",
            },
        ),
        Chunk(
            chunk_id="doc-tech:1",
            document_id="doc-tech",
            chunk_index=1,
            content="Services communicate via REST APIs and message queues.",
            metadata={
                "file_name": "architecture.txt",
                "file_type": "txt",
                "source": "docs/architecture.txt",
                "section": "Communication",
            },
        ),
    ]

    results = embedding_service.embed_texts([c.content for c in chunks])
    vectors = [r.embedding for r in results]
    store.upsert_chunks(chunks=chunks, embeddings=vectors)
    return store


@pytest.fixture(scope="module")
def retriever(
    memory_client: QdrantClient,
    embedding_service: EmbeddingService,
) -> DenseRetriever:
    """DenseRetriever pointed at the in-memory collection."""
    return DenseRetriever(
        embedding_service=embedding_service,
        qdrant_client=memory_client,
        collection_name=INTEG_COLLECTION,
        vector_size=INTEG_DIM,
        max_top_k=100,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDenseRetrieverIntegration:
    """End-to-end dense retrieval tests against in-memory Qdrant."""

    def test_retrieval_returns_list(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("casual leave days", top_k=3)
        assert isinstance(results, list)

    def test_retrieval_returns_up_to_top_k(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave days", top_k=3)
        assert len(results) <= 3

    def test_retrieval_returns_retrieval_result_instances(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave", top_k=5)
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_results_have_scores(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave policy", top_k=5)
        assert all(isinstance(r.score, float) for r in results)

    def test_results_have_content(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave policy", top_k=5)
        assert all(len(r.content) > 0 for r in results)

    def test_results_have_document_id(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave policy", top_k=5)
        assert all(r.document_id != "" for r in results)

    def test_results_have_chunk_id(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave policy", top_k=5)
        assert all(r.chunk_id != "" for r in results)

    def test_scores_are_in_descending_order(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        """Qdrant returns results in descending similarity order."""
        results = retriever.retrieve("leave policy", top_k=5)
        if len(results) > 1:
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_document_id_filter_restricts_results(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        """Filter by document_id should return only chunks from that document."""
        f = RetrievalFilter(document_id="doc-hr")
        results = retriever.retrieve("leave", top_k=10, filters=f)
        assert len(results) > 0
        assert all(r.document_id == "doc-hr" for r in results)

    def test_file_type_filter_restricts_results(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        f = RetrievalFilter(file_type="txt")
        results = retriever.retrieve("system architecture", top_k=10, filters=f)
        assert len(results) > 0
        assert all(r.file_type == "txt" for r in results)

    def test_source_filter_restricts_results(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        f = RetrievalFilter(source="docs/architecture.txt")
        results = retriever.retrieve("services", top_k=10, filters=f)
        assert len(results) > 0
        assert all(r.source == "docs/architecture.txt" for r in results)

    def test_non_matching_filter_returns_empty(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        f = RetrievalFilter(document_id="non-existent-document-xyz")
        results = retriever.retrieve("leave", top_k=10, filters=f)
        assert results == []

    def test_top_k_one_returns_single_result(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave", top_k=1)
        assert len(results) == 1

    def test_file_name_in_result(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        results = retriever.retrieve("leave", top_k=3)
        assert all(r.file_name != "" for r in results)

    def test_section_in_result(
        self,
        populated_store: QdrantVectorStore,
        retriever: DenseRetriever,
    ) -> None:
        f = RetrievalFilter(document_id="doc-hr")
        results = retriever.retrieve("leave", top_k=3, filters=f)
        assert all(r.section == "Leave Policy" for r in results)
