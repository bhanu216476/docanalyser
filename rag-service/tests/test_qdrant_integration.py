"""
Integration tests for Qdrant vector store against a live Qdrant instance.

Checks if a live Qdrant service is reachable at the configured URL (http://localhost:6333).
If available (e.g. Docker container is running), executes real network upsert, count,
and filter operations. If unreachable, gracefully skips to maintain hermetic test runs.
"""

from __future__ import annotations

import socket
import pytest
from qdrant_client import QdrantClient

from app.core.config import settings
from app.ingestion.chunking.models import Chunk
from app.vector_store import (
    QdrantVectorStore,
    VectorStoreFilter,
    create_qdrant_client,
)

INTEGRATION_COLLECTION = "docanalyser_integration_test_collection"
INTEGRATION_DIM = 8


def is_qdrant_live(host: str = "localhost", port: int = 6333, timeout: float = 0.5) -> bool:
    """Check if Qdrant TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionError):
        return False


@pytest.mark.integration
class TestQdrantDockerIntegration:
    """Integration test suite executing against a live Qdrant container."""

    @pytest.fixture(autouse=True)
    def check_live_qdrant(self) -> None:
        """Skip integration tests if Docker Qdrant service is not running."""
        if not is_qdrant_live():
            pytest.skip(
                "Live Qdrant instance not reachable on localhost:6333. "
                "Start with 'docker-compose up qdrant' to run integration tests."
            )

    @pytest.fixture
    def live_store(self) -> QdrantVectorStore:
        """Provide a store connected to the live Qdrant instance."""
        client = create_qdrant_client(url=settings.qdrant_url)
        store = QdrantVectorStore(
            client=client,
            collection_name=INTEGRATION_COLLECTION,
            vector_size=INTEGRATION_DIM,
            distance="Cosine",
        )
        # Ensure clean state for test
        store.ensure_collection()
        yield store
        # Cleanup test collection after test to avoid littering
        try:
            client.delete_collection(INTEGRATION_COLLECTION)
        except Exception:
            pass

    def test_live_qdrant_round_trip(self, live_store: QdrantVectorStore) -> None:
        """Verify collection creation, vector upsert, count, and deletion on live Qdrant."""
        chunk = Chunk(
            chunk_id="live-doc:0",
            document_id="live-doc",
            content="Integration test chunk content.",
            chunk_index=0,
            metadata={
                "file_name": "live.md",
                "file_type": "md",
                "source": "tests/live.md",
            },
        )
        vector = [0.1] * INTEGRATION_DIM

        # Upsert
        count = live_store.upsert_chunks(chunks=[chunk], embeddings=[vector])
        assert count == 1
        assert live_store.count() == 1

        # Query with filter
        doc_count = live_store.count(filter_spec=VectorStoreFilter(document_id="live-doc"))
        assert doc_count == 1

        # Delete
        live_store.delete_by_document_id("live-doc")
        assert live_store.count() == 0
