"""
Unit and integration tests for BM25Retriever and API endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.api.retrieval import set_bm25_retriever
from app.chunking.models import Chunk as ChunkModel
from app.ingestion.chunking.models import Chunk as IngestionChunk
from app.main import app
from app.retrieval import (
    BM25Retriever,
    RetrievalFilter,
    RetrievalQueryError,
    RetrievalRequest,
    Retriever,
    create_bm25_retriever,
)


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Sample chunk fixture covering multiple documents and topics."""
    return [
        {
            "chunk_id": "hr_doc_1:0",
            "document_id": "hr_doc_1",
            "content": "Employees are entitled to 12 days of casual leave per calendar year.",
            "file_name": "leave_policy.md",
            "file_type": "md",
            "source": "/docs/hr/leave_policy.md",
            "section": "Casual Leave",
            "chunk_index": 0,
            "metadata": {"dept": "HR"},
        },
        {
            "chunk_id": "hr_doc_1:1",
            "document_id": "hr_doc_1",
            "content": "Employees are entitled to 15 days of sick leave with medical certificate.",
            "file_name": "leave_policy.md",
            "file_type": "md",
            "source": "/docs/hr/leave_policy.md",
            "section": "Sick Leave",
            "chunk_index": 1,
            "metadata": {"dept": "HR"},
        },
        {
            "chunk_id": "it_doc_1:0",
            "document_id": "it_doc_1",
            "content": "All laptops must have disk encryption and antivirus software installed.",
            "file_name": "security.txt",
            "file_type": "txt",
            "source": "/docs/it/security.txt",
            "section": "Device Policy",
            "chunk_index": 0,
            "metadata": {"dept": "IT"},
        },
        {
            "chunk_id": "it_doc_1:1",
            "document_id": "it_doc_1",
            "content": "Remote access requires multi factor authentication and VPN connection.",
            "file_name": "security.txt",
            "file_type": "txt",
            "source": "/docs/it/security.txt",
            "section": "Remote Access",
            "chunk_index": 1,
            "metadata": {"dept": "IT"},
        },
    ]


@pytest.fixture
def populated_retriever(sample_chunks: list[dict]) -> BM25Retriever:
    return create_bm25_retriever(chunks=sample_chunks)


class TestBM25RetrieverProtocolAndBehavior:
    """Verification that BM25Retriever satisfies Retriever protocol and requirements."""

    def test_satisfies_retriever_protocol(self, populated_retriever: BM25Retriever) -> None:
        """BM25Retriever conforms structurally to the Retriever protocol."""
        assert isinstance(populated_retriever, Retriever)

    def test_ranking_and_scores(self, populated_retriever: BM25Retriever) -> None:
        """Results are returned in descending BM25 score order with 1-based ranks."""
        results = populated_retriever.retrieve("casual leave", top_k=5)
        assert len(results) >= 1

        # Check descending scores
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

        # Most relevant is hr_doc_1:0
        assert results[0].chunk_id == "hr_doc_1:0"
        assert results[0].rank == 1
        assert "casual leave" in results[0].content.lower()

        # Check metadata preservation
        assert results[0].document_id == "hr_doc_1"
        assert results[0].file_type == "md"
        assert results[0].section == "Casual Leave"
        assert results[0].metadata.get("dept") == "HR"

    def test_top_k_truncation(self, populated_retriever: BM25Retriever) -> None:
        """top_k restricts the number of returned results."""
        res_top1 = populated_retriever.retrieve("leave", top_k=1)
        assert len(res_top1) == 1

        res_top2 = populated_retriever.retrieve("leave", top_k=2)
        assert len(res_top2) == 2

    def test_top_k_validation(self, populated_retriever: BM25Retriever) -> None:
        """Invalid top_k values raise RetrievalQueryError."""
        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve("leave", top_k=0)

        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve("leave", top_k=-5)

        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve("leave", top_k=1000)  # exceeds max_top_k (100)

    def test_query_validation(self, populated_retriever: BM25Retriever) -> None:
        """Empty or whitespace-only queries raise RetrievalQueryError."""
        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve("")

        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve("   ")

        with pytest.raises(RetrievalQueryError):
            populated_retriever.retrieve(None)  # type: ignore[arg-type]

    def test_unknown_terms_return_empty(self, populated_retriever: BM25Retriever) -> None:
        """Query with terms nonexistent in corpus returns empty list deterministically."""
        results = populated_retriever.retrieve("xyzabc123 qwerty987")
        assert results == []

    def test_empty_corpus_returns_empty(self) -> None:
        """Retriever on empty corpus safely returns empty list."""
        empty_retriever = create_bm25_retriever()
        results = empty_retriever.retrieve("casual leave")
        assert results == []

    def test_pre_ranking_metadata_filtering(self, populated_retriever: BM25Retriever) -> None:
        """Metadata filters are applied before ranking."""
        # Query matches both MD (HR) and TXT (IT) if unconstrained,
        # but filter by file_type='txt'
        filter_txt = RetrievalFilter(file_type="txt")
        results_txt = populated_retriever.retrieve("encryption access", filters=filter_txt)
        assert len(results_txt) > 0
        for r in results_txt:
            assert r.file_type == "txt"

        # Filter by document_id
        filter_doc = RetrievalFilter(document_id="hr_doc_1")
        results_hr = populated_retriever.retrieve("leave", filters=filter_doc)
        assert len(results_hr) == 2
        for r in results_hr:
            assert r.document_id == "hr_doc_1"

        # Filter by section
        filter_sec = RetrievalFilter(section="Device Policy")
        results_sec = populated_retriever.retrieve("encryption", filters=filter_sec)
        assert len(results_sec) == 1
        assert results_sec[0].chunk_id == "it_doc_1:0"

    def test_deterministic_tie_breaking(self) -> None:
        """Chunks with identical BM25 scores break ties deterministically by chunk_id."""
        identical_chunks = [
            {"chunk_id": "chunk_z", "content": "identical content for testing"},
            {"chunk_id": "chunk_a", "content": "identical content for testing"},
            {"chunk_id": "chunk_m", "content": "identical content for testing"},
        ]
        retriever = create_bm25_retriever(chunks=identical_chunks)

        results = retriever.retrieve("identical content", top_k=3)
        assert len(results) == 3

        # Scores should be identical
        assert results[0].score == results[1].score == results[2].score

        # Ordered deterministically by chunk_id ascending: chunk_a, chunk_m, chunk_z
        assert [r.chunk_id for r in results] == ["chunk_a", "chunk_m", "chunk_z"]

    def test_support_for_chunk_models(self) -> None:
        """Supports indexing Chunk Pydantic model instances."""
        chunk1 = IngestionChunk(
            chunk_id="ingest_1",
            document_id="doc_ingest",
            content="Ingestion chunk test text",
            chunk_index=0,
            metadata={"source": "test"},
        )
        retriever = create_bm25_retriever(chunks=[chunk1])
        results = retriever.retrieve("ingestion", top_k=1)
        assert len(results) == 1
        assert results[0].chunk_id == "ingest_1"


class TestBM25APIEndpoint:
    """Test suite for FastAPI POST /api/retrieval/bm25 endpoint."""

    @pytest.fixture(autouse=True)
    def setup_endpoint(self, sample_chunks: list[dict]) -> None:
        retriever = create_bm25_retriever(chunks=sample_chunks)
        set_bm25_retriever(retriever)

    def test_api_bm25_success(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/retrieval/bm25",
            json={"query": "casual leave", "top_k": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["chunk_id"] == "hr_doc_1:0"
        assert data[0]["rank"] == 1
        assert data[0]["score"] > 0.0

    def test_api_bm25_with_filter(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/retrieval/bm25",
            json={
                "query": "leave",
                "top_k": 5,
                "filters": {"section": "Sick Leave"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["chunk_id"] == "hr_doc_1:1"

    def test_api_bm25_empty_query_422(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/retrieval/bm25",
            json={"query": "   ", "top_k": 5},
        )
        assert response.status_code == 422
