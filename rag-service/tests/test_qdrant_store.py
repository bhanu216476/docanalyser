"""
Unit tests for Qdrant vector storage module.

Uses the in-memory Qdrant client (:memory:) to ensure 100% deterministic,
fast, and hermetic tests without requiring external Docker services or network calls.

Coverage:
    - Collection creation (idempotent, creation vs no-recreation)
    - Collection configuration validation (dimension mismatch, distance metric mismatch)
    - Vector geometry & numeric validation
    - Alignment & count validation between chunks and embeddings
    - Batched vector insertion and order preservation
    - Idempotent upsert semantics via deterministic UUIDv5 IDs
    - Traceable metadata payload structure and typing
    - Native Qdrant filter building (document_id, file_type, source, compound AND/OR)
    - Filter field whitelist validation
    - Document deletion for re-ingestion
    - Transient error retry logic
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from qdrant_client import QdrantClient, models

from app.embeddings.models import EmbeddingResult
from app.ingestion.chunking.models import Chunk
from app.vector_store import (
    ALLOWED_FILTER_FIELDS,
    CollectionConfigError,
    FilterBuilder,
    FilterValidationError,
    QdrantVectorStore,
    VectorPayload,
    VectorPoint,
    VectorStoreConnectionError,
    VectorStoreFilter,
    VectorValidationError,
    build_payload_from_chunk,
    generate_point_id,
)

# Test dimension for fake vectors
TEST_DIMENSION = 8


@pytest.fixture
def memory_client() -> QdrantClient:
    """Provide a fresh in-memory Qdrant client for each test."""
    return QdrantClient(":memory:")


@pytest.fixture
def store(memory_client: QdrantClient) -> QdrantVectorStore:
    """Provide a QdrantVectorStore configured with in-memory client and 8-dim vectors."""
    return QdrantVectorStore(
        client=memory_client,
        collection_name="test_documents",
        vector_size=TEST_DIMENSION,
        distance="Cosine",
        batch_size=4,
        max_retries=2,
        retry_base_delay=0.01,
    )


def make_chunk(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    content: str = "Sample chunk text for testing.",
    file_name: str = "handbook.md",
    file_type: str = "md",
    source: str = "docs/handbook.md",
    section: str | None = "Introduction",
    headings: list[str] | None = None,
) -> Chunk:
    """Helper to construct a valid domain Chunk."""
    return Chunk(
        chunk_id=f"{document_id}:{chunk_index}",
        document_id=document_id,
        content=content,
        chunk_index=chunk_index,
        start_char=0,
        end_char=len(content),
        metadata={
            "file_name": file_name,
            "file_type": file_type,
            "source": source,
            "section": section,
            "headings": headings or ["Introduction"],
        },
    )


def make_vector(seed: float = 0.1, dim: int = TEST_DIMENSION) -> list[float]:
    """Helper to generate a valid normalized float vector."""
    return [round(seed + i * 0.05, 4) for i in range(dim)]


# ===========================================================================
# 1. Collection Lifecycle & Validation Tests (Requirements 6, 8, 9, 10)
# ===========================================================================


def test_1_collection_does_not_exist_creates_collection(store: QdrantVectorStore) -> None:
    """Test 1: If collection does not exist, it is created with proper config."""
    assert not store._client.collection_exists("test_documents")

    created = store.ensure_collection()
    assert created is True
    assert store._client.collection_exists("test_documents")

    info = store._client.get_collection("test_documents")
    assert info.config.params.vectors.size == TEST_DIMENSION
    assert info.config.params.vectors.distance == models.Distance.COSINE


def test_2_collection_already_exists_no_recreation(store: QdrantVectorStore) -> None:
    """Test 2: If collection already exists and matches config, it is not recreated."""
    store.ensure_collection()
    assert store._client.collection_exists("test_documents")

    # Second call should return False (already exists and valid)
    created = store.ensure_collection()
    assert created is False


def test_3_existing_collection_wrong_vector_dimension_raises_error(
    store: QdrantVectorStore,
) -> None:
    """Test 3: Existing collection with incompatible vector dimension raises CollectionConfigError."""
    # Create collection with dimension 16
    store._client.create_collection(
        collection_name="test_documents",
        vectors_config=models.VectorParams(size=16, distance=models.Distance.COSINE),
    )

    # Store expects dimension 8 (TEST_DIMENSION)
    with pytest.raises(CollectionConfigError) as exc_info:
        store.ensure_collection()

    assert "vector dimension mismatch" in str(exc_info.value).lower()
    assert "16" in str(exc_info.value)
    assert str(TEST_DIMENSION) in str(exc_info.value)


def test_4_existing_collection_incompatible_distance_raises_error(
    store: QdrantVectorStore,
) -> None:
    """Test 4: Existing collection with incompatible distance metric raises CollectionConfigError."""
    # Create collection with Euclidean distance
    store._client.create_collection(
        collection_name="test_documents",
        vectors_config=models.VectorParams(size=TEST_DIMENSION, distance=models.Distance.EUCLID),
    )

    # Store expects Cosine distance
    with pytest.raises(CollectionConfigError) as exc_info:
        store.ensure_collection()

    assert "distance metric mismatch" in str(exc_info.value).lower()


# ===========================================================================
# 2. Vector Insertion & Batching Tests (Requirements 12, 13, 14, 15, 24)
# ===========================================================================


def test_5_valid_vector_insertion(store: QdrantVectorStore) -> None:
    """Test 5: Valid chunk and vector are successfully stored and retrieved."""
    store.ensure_collection()

    chunk = make_chunk(document_id="doc-1", chunk_index=0, content="Single chunk text.")
    vector = make_vector(0.1)

    count = store.upsert_chunks(chunks=[chunk], embeddings=[vector])
    assert count == 1
    assert store.count() == 1

    # Verify stored record
    record = store.get_point(chunk.chunk_id)
    assert record is not None
    assert record.id == generate_point_id(chunk.chunk_id)
    assert record.payload["document_id"] == "doc-1"
    assert record.payload["content"] == "Single chunk text."
    assert record.payload["file_type"] == "md"


def test_6_multiple_vectors_inserted_in_batches(store: QdrantVectorStore) -> None:
    """Test 6: Multiple vectors (greater than batch_size=4) inserted across multiple batches."""
    store.ensure_collection()

    total_chunks = 10
    chunks = [
        make_chunk(document_id="doc-multi", chunk_index=i, content=f"Batch chunk content {i}")
        for i in range(total_chunks)
    ]
    embeddings = [make_vector(0.01 * (i + 1)) for i in range(total_chunks)]

    count = store.upsert_chunks(chunks=chunks, embeddings=embeddings, batch_size=4)
    assert count == total_chunks
    assert store.count() == total_chunks

    # Verify each point is present
    for chunk in chunks:
        rec = store.get_point(chunk.chunk_id)
        assert rec is not None
        assert rec.payload["chunk_id"] == chunk.chunk_id


def test_7_chunk_embedding_count_mismatch_raises_validation_error(
    store: QdrantVectorStore,
) -> None:
    """Test 7: Mismatch between chunk count and embedding count raises VectorValidationError."""
    store.ensure_collection()

    chunks = [make_chunk(chunk_index=0), make_chunk(chunk_index=1)]
    embeddings = [make_vector(0.1)]  # Only 1 embedding for 2 chunks

    with pytest.raises(VectorValidationError) as exc_info:
        store.upsert_chunks(chunks=chunks, embeddings=embeddings)

    assert "count" in str(exc_info.value).lower()
    assert "mismatch" in str(exc_info.value).lower()


def test_8_incorrect_vector_dimension_raises_validation_error(
    store: QdrantVectorStore,
) -> None:
    """Test 8: Vector with wrong dimension is rejected before insertion."""
    store.ensure_collection()

    chunk = make_chunk()
    wrong_dim_vector = [0.1, 0.2, 0.3]  # Length 3 instead of TEST_DIMENSION (8)

    with pytest.raises(VectorValidationError) as exc_info:
        store.upsert_chunks(chunks=[chunk], embeddings=[wrong_dim_vector])

    assert "dimension" in str(exc_info.value).lower()


def test_9_repeated_insertion_is_idempotent(store: QdrantVectorStore) -> None:
    """Test 9: Inserting the exact same chunk multiple times updates in-place (no duplicates)."""
    store.ensure_collection()

    chunk = make_chunk(document_id="doc-idempotent", chunk_index=0, content="Initial content.")
    vector_v1 = make_vector(0.1)

    # First insertion
    store.upsert_chunks(chunks=[chunk], embeddings=[vector_v1])
    assert store.count() == 1

    # Second insertion with same chunk_id, updated content
    updated_chunk = make_chunk(
        document_id="doc-idempotent", chunk_index=0, content="Updated content."
    )
    vector_v2 = make_vector(0.2)

    store.upsert_chunks(chunks=[updated_chunk], embeddings=[vector_v2])

    # Count must STILL be 1, not 2!
    assert store.count() == 1

    record = store.get_point(chunk.chunk_id)
    assert record is not None
    assert record.payload["content"] == "Updated content."


def test_non_numeric_vector_raises_validation_error(store: QdrantVectorStore) -> None:
    """Vectors containing strings, None, NaN, or Inf are rejected."""
    store.ensure_collection()
    chunk = make_chunk()

    # Vector with string element
    invalid_vector: list = [0.1, 0.2, "bad_val", 0.4, 0.5, 0.6, 0.7, 0.8]
    with pytest.raises(VectorValidationError):
        store.upsert_chunks(chunks=[chunk], embeddings=[invalid_vector])

    # Vector with NaN
    nan_vector = [0.1, 0.2, float("nan"), 0.4, 0.5, 0.6, 0.7, 0.8]
    with pytest.raises(VectorValidationError):
        store.upsert_chunks(chunks=[chunk], embeddings=[nan_vector])


def test_embedding_result_object_accepted(store: QdrantVectorStore) -> None:
    """upsert_chunks seamlessly accepts EmbeddingResult objects from EmbeddingService."""
    store.ensure_collection()
    chunk = make_chunk()
    emb_result = EmbeddingResult(
        index=0,
        embedding=make_vector(0.15),
        token_count=12,
    )

    count = store.upsert_chunks(chunks=[chunk], embeddings=[emb_result])
    assert count == 1
    assert store.count() == 1


# ===========================================================================
# 3. Payload Metadata Tests (Requirements 16, 17, 18, 19, 20)
# ===========================================================================


def test_15_payload_structure_contains_all_traceability_fields(
    store: QdrantVectorStore,
) -> None:
    """Test 15: Stored point payload contains all required provenance & content fields."""
    store.ensure_collection()

    chunk = make_chunk(
        document_id="doc-xyz",
        chunk_index=3,
        content="Important policy excerpt.",
        file_name="policy.md",
        file_type="md",
        source="/company/policy.md",
        section="Refunds",
        headings=["Finance", "Refunds"],
    )
    vector = make_vector(0.5)

    store.upsert_chunks(chunks=[chunk], embeddings=[vector])

    record = store.get_point(chunk.chunk_id)
    assert record is not None
    payload = record.payload

    # Core required traceability fields
    assert payload["document_id"] == "doc-xyz"
    assert payload["chunk_id"] == "doc-xyz:3"
    assert payload["chunk_index"] == 3
    assert payload["file_name"] == "policy.md"
    assert payload["file_type"] == "md"
    assert payload["source"] == "/company/policy.md"
    assert payload["content"] == "Important policy excerpt."
    assert payload["section"] == "Refunds"
    assert payload["headings"] == ["Finance", "Refunds"]

    # Verify types are simple, filter-compatible
    assert isinstance(payload["document_id"], str)
    assert isinstance(payload["chunk_index"], int)
    assert isinstance(payload["file_type"], str)
    assert isinstance(payload["source"], str)


def test_vector_payload_model_validation() -> None:
    """VectorPayload strictly enforces non-empty content and type constraints."""
    # Empty content should be rejected
    with pytest.raises(ValueError):
        VectorPayload(
            document_id="doc-1",
            chunk_id="doc-1:0",
            chunk_index=0,
            file_name="test.txt",
            file_type="txt",
            source="test.txt",
            content="   ",  # Whitespace only
        )


# ===========================================================================
# 4. Metadata Filter Tests (Requirements 21, 22)
# ===========================================================================


def test_10_filter_by_document_id(store: QdrantVectorStore) -> None:
    """Test 10: Filter by document_id matches only points from that document."""
    store.ensure_collection()

    chunk1 = make_chunk(document_id="doc-A", chunk_index=0)
    chunk2 = make_chunk(document_id="doc-B", chunk_index=0)
    store.upsert_chunks(chunks=[chunk1, chunk2], embeddings=[make_vector(0.1), make_vector(0.2)])

    filter_doc_a = VectorStoreFilter(document_id="doc-A")
    assert store.count(filter_spec=filter_doc_a) == 1

    filter_doc_b = VectorStoreFilter(document_id="doc-B")
    assert store.count(filter_spec=filter_doc_b) == 1

    filter_doc_c = VectorStoreFilter(document_id="doc-C")
    assert store.count(filter_spec=filter_doc_c) == 0


def test_11_filter_by_file_type(store: QdrantVectorStore) -> None:
    """Test 11: Filter by file_type."""
    store.ensure_collection()

    chunk_md = make_chunk(document_id="doc-1", chunk_index=0, file_type="md")
    chunk_txt = make_chunk(document_id="doc-2", chunk_index=0, file_type="txt")
    store.upsert_chunks(
        chunks=[chunk_md, chunk_txt], embeddings=[make_vector(0.1), make_vector(0.2)]
    )

    assert store.count(filter_spec=VectorStoreFilter(file_type="md")) == 1
    assert store.count(filter_spec=VectorStoreFilter(file_type="txt")) == 1
    assert store.count(filter_spec=VectorStoreFilter(file_type="pdf")) == 0


def test_12_filter_by_source(store: QdrantVectorStore) -> None:
    """Test 12: Filter by source URI/path."""
    store.ensure_collection()

    chunk1 = make_chunk(document_id="doc-1", source="s3://bucket/docs/spec.md")
    chunk2 = make_chunk(document_id="doc-2", source="local://files/notes.txt")
    store.upsert_chunks(chunks=[chunk1, chunk2], embeddings=[make_vector(0.1), make_vector(0.2)])

    assert store.count(filter_spec=VectorStoreFilter(source="s3://bucket/docs/spec.md")) == 1
    assert store.count(filter_spec=VectorStoreFilter(source="local://files/notes.txt")) == 1
    assert store.count(filter_spec=VectorStoreFilter(source="unknown")) == 0


def test_13_combined_filters_and_logic(store: QdrantVectorStore) -> None:
    """Test 13: Combined filters (e.g. document_id AND file_type)."""
    store.ensure_collection()

    c1 = make_chunk(document_id="doc-X", chunk_index=0, file_type="md")
    c2 = make_chunk(document_id="doc-X", chunk_index=1, file_type="md")
    c3 = make_chunk(document_id="doc-Y", chunk_index=0, file_type="txt")

    store.upsert_chunks(
        chunks=[c1, c2, c3],
        embeddings=[make_vector(0.1), make_vector(0.2), make_vector(0.3)],
    )

    # document_id='doc-X' AND file_type='md' -> 2
    f1 = VectorStoreFilter(document_id="doc-X", file_type="md")
    assert store.count(filter_spec=f1) == 2

    # document_id='doc-X' AND file_type='txt' -> 0
    f2 = VectorStoreFilter(document_id="doc-X", file_type="txt")
    assert store.count(filter_spec=f2) == 0


def test_14_invalid_filter_field_raises_validation_error() -> None:
    """Test 14: Unauthorized or illegal filter field raises FilterValidationError."""
    # Attempt to filter by an arbitrary un-indexed field
    with pytest.raises(FilterValidationError) as exc_info:
        FilterBuilder.build({"unsupported_random_field": "some_value"})

    assert "invalid filter field" in str(exc_info.value).lower()
    assert "unsupported_random_field" in str(exc_info.value)

    # In VectorStoreFilter custom_filters
    with pytest.raises(FilterValidationError):
        FilterBuilder.build(
            VectorStoreFilter(custom_filters={"unapproved_key": 123})
        )


def test_filter_builder_match_any_for_list_values() -> None:
    """FilterBuilder constructs MatchAny condition when a list of values is passed."""
    q_filter = FilterBuilder.build(VectorStoreFilter(document_id=["doc-1", "doc-2"]))
    assert q_filter is not None
    assert len(q_filter.must) == 1
    cond = q_filter.must[0]
    assert cond.key == "document_id"
    assert isinstance(cond.match, models.MatchAny)
    assert cond.match.any == ["doc-1", "doc-2"]


# ===========================================================================
# 5. Document Deletion Tests (Requirement 23)
# ===========================================================================


def test_18_delete_by_document_id(store: QdrantVectorStore) -> None:
    """Test 18: Deleting by document_id removes all chunks of that document, preserving others."""
    store.ensure_collection()

    chunks_doc1 = [make_chunk(document_id="doc-to-delete", chunk_index=i) for i in range(3)]
    chunks_doc2 = [make_chunk(document_id="doc-to-keep", chunk_index=i) for i in range(2)]

    all_chunks = chunks_doc1 + chunks_doc2
    all_embs = [make_vector(0.05 * i) for i in range(len(all_chunks))]

    store.upsert_chunks(chunks=all_chunks, embeddings=all_embs)
    assert store.count() == 5

    # Delete doc-to-delete
    store.delete_by_document_id("doc-to-delete")

    assert store.count() == 2
    assert store.count(filter_spec=VectorStoreFilter(document_id="doc-to-delete")) == 0
    assert store.count(filter_spec=VectorStoreFilter(document_id="doc-to-keep")) == 2


def test_delete_by_empty_document_id_raises_validation_error(
    store: QdrantVectorStore,
) -> None:
    """Empty or whitespace document_id is rejected for deletion."""
    with pytest.raises(VectorValidationError):
        store.delete_by_document_id("   ")


# ===========================================================================
# 6. Retry & Transient Error Tests (Requirement 26)
# ===========================================================================


def test_transient_error_retries_and_succeeds(store: QdrantVectorStore) -> None:
    """Transient errors during batch upsert are retried and succeed on recovery."""
    store.ensure_collection()
    chunk = make_chunk()
    vector = make_vector(0.1)

    call_count = 0
    real_upsert = store._client.upsert

    def flaky_upsert(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Simulated transient socket reset")
        return real_upsert(*args, **kwargs)

    with patch.object(store._client, "upsert", side_effect=flaky_upsert):
        count = store.upsert_chunks(chunks=[chunk], embeddings=[vector])
        assert count == 1
        assert call_count == 2  # Failed once, retried and succeeded


def test_permanent_error_not_retried(store: QdrantVectorStore) -> None:
    """Permanent errors (e.g. 400 Bad Request) fail immediately without exhausting retries."""
    store.ensure_collection()
    chunk = make_chunk()
    vector = make_vector(0.1)

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.content = b"Bad Request: invalid parameter"

    from qdrant_client.http.exceptions import UnexpectedResponse
    exc = UnexpectedResponse(status_code=400, reason_phrase="Bad Request", content=b"Bad Request", headers={})

    with patch.object(store._client, "upsert", side_effect=exc):
        from app.vector_store.exceptions import VectorStoreBatchError
        with pytest.raises(VectorStoreBatchError):
            store.upsert_chunks(chunks=[chunk], embeddings=[vector])
