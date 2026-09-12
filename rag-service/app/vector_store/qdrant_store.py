"""
Qdrant vector store implementation for collection management and vector persistence.

Pipeline position:
    EmbeddingService (EmbeddingResult[]) + Chunk[]
                     ↓
             QdrantVectorStore  ◄── [This Component]
                     ↓
              Qdrant Client
                     ↓
             Qdrant Collection

Responsibilities:
    ✓ Idempotent collection creation with vector size and distance configuration
    ✓ Existing collection schema validation (vector dimension and distance metric)
    ✓ Automatic creation of payload indexes on filterable fields
    ✓ Deterministic point ID assignment (UUIDv5) ensuring idempotency
    ✓ Upfront vector geometry and type validation (dimension, numeric, non-empty)
    ✓ Preservation of chunk-embedding alignment and ordering
    ✓ Structured, traceable metadata payloads with chunk text content
    ✓ Batched vector upserting with bounded exponential backoff retry for transient failures
    ✓ Document-level chunk deletion for safe re-ingestion workflows
    ✓ Controlled metadata filter translation using native Qdrant models

Strictly Out of Scope:
    ✗ Vector similarity search / retrieval
    ✗ BM25 / Sparse retrieval
    ✗ Hybrid fusion / RRF
    ✗ Reranking
    ✗ LLM integration
"""

from __future__ import annotations

from collections.abc import Sequence
import logging
import math
import random
import time
from typing import Any, Optional, Union

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.core.config import settings
from app.embeddings.models import EmbeddingResult
from app.ingestion.chunking.models import Chunk
from app.vector_store.exceptions import (
    CollectionConfigError,
    VectorStoreBatchError,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorValidationError,
)
from app.vector_store.filters import FilterBuilder, VectorStoreFilter
from app.vector_store.models import (
    VectorPayload,
    VectorPoint,
    build_payload_from_chunk,
    generate_point_id,
)
from app.vector_store.qdrant_client import create_qdrant_client

logger = logging.getLogger(__name__)

# Jitter range for retries (seconds)
_JITTER_MAX: float = 0.1


def _resolve_distance(distance: Union[str, models.Distance]) -> models.Distance:
    """
    Convert a string or Distance enum to a native Qdrant Distance enum.

    Args:
        distance: Distance name ('Cosine', 'Dot', 'Euclid', etc.) or Distance enum.

    Returns:
        models.Distance enum value.

    Raises:
        CollectionConfigError: If distance metric name is unrecognized.
    """
    if isinstance(distance, models.Distance):
        return distance

    dist_map = {
        "cosine": models.Distance.COSINE,
        "dot": models.Distance.DOT,
        "euclid": models.Distance.EUCLID,
        "manhattan": models.Distance.MANHATTAN,
    }
    normalized = distance.strip().lower()
    if normalized not in dist_map:
        raise CollectionConfigError(
            f"Unsupported distance metric '{distance}'. Supported metrics: {list(dist_map.keys())}"
        )
    return dist_map[normalized]


class QdrantVectorStore:
    """
    Production-grade storage layer for Qdrant vector database.

    Provides a clean domain abstraction over the low-level QdrantClient.
    """

    def __init__(
        self,
        client: Optional[QdrantClient] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        distance: Optional[Union[str, models.Distance]] = None,
        batch_size: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_base_delay: Optional[float] = None,
    ) -> None:
        """
        Initialize the QdrantVectorStore.

        Args:
            client: Optional QdrantClient instance. If None, created via ``create_qdrant_client()``.
            collection_name: Name of collection. Defaults to ``settings.qdrant_collection_name``.
            vector_size: Dimension of embeddings. Defaults to ``settings.qdrant_vector_size`` (1536).
            distance: Distance metric ('Cosine', 'Dot', etc.). Defaults to ``settings.qdrant_distance``.
            batch_size: Points per upsert request. Defaults to ``settings.qdrant_batch_size`` (64).
            max_retries: Retry attempts for transient failures. Defaults to ``settings.qdrant_max_retries`` (3).
            retry_base_delay: Base seconds for exponential backoff. Defaults to ``settings.qdrant_retry_base_delay`` (0.5).
        """
        self._client = client if client is not None else create_qdrant_client()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.vector_size = vector_size or settings.qdrant_vector_size
        self.distance = _resolve_distance(distance or settings.qdrant_distance)
        self.batch_size = batch_size or settings.qdrant_batch_size
        self.max_retries = max_retries if max_retries is not None else settings.qdrant_max_retries
        self.retry_base_delay = (
            retry_base_delay if retry_base_delay is not None else settings.qdrant_retry_base_delay
        )

        logger.info(
            "QdrantVectorStore initialized: collection='%s', vector_size=%d, distance=%s, batch_size=%d",
            self.collection_name,
            self.vector_size,
            self.distance.value,
            self.batch_size,
        )

    # -----------------------------------------------------------------------
    # Collection Lifecycle & Validation
    # -----------------------------------------------------------------------

    def ensure_collection(
        self,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        distance: Optional[Union[str, models.Distance]] = None,
    ) -> bool:
        """
        Idempotently verify or create a collection with payload indexes.

        Behavior:
            - If collection does NOT exist: creates it with specified dimensions,
              distance metric, and standard payload indexes.
            - If collection DOES exist: validates that its configuration matches
              the required vector dimension and distance metric.
            - NEVER deletes or blindly recreates an existing collection.

        Args:
            collection_name: Collection name override. Defaults to instance collection_name.
            vector_size: Vector dimension override. Defaults to instance vector_size.
            distance: Distance metric override. Defaults to instance distance.

        Returns:
            True if a new collection was created; False if an existing collection was verified.

        Raises:
            CollectionConfigError: If existing collection configuration does not match.
            VectorStoreConnectionError: If Qdrant cannot be reached.
        """
        target_name = collection_name or self.collection_name
        target_size = vector_size or self.vector_size
        target_distance = _resolve_distance(distance or self.distance)

        try:
            exists = self._client.collection_exists(target_name)
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Failed to check existence of Qdrant collection '{target_name}': {exc}"
            ) from exc

        if not exists:
            logger.info(
                "Creating Qdrant collection '%s' (size=%d, distance=%s)",
                target_name,
                target_size,
                target_distance.value,
            )
            try:
                self._client.create_collection(
                    collection_name=target_name,
                    vectors_config=models.VectorParams(
                        size=target_size,
                        distance=target_distance,
                    ),
                )
            except Exception as exc:
                raise VectorStoreError(
                    f"Failed to create Qdrant collection '{target_name}': {exc}"
                ) from exc

            # Create payload indexes on commonly filtered fields
            self._create_payload_indexes(target_name)
            return True

        # Existing collection found — validate compatibility
        self._validate_existing_collection(
            collection_name=target_name,
            expected_size=target_size,
            expected_distance=target_distance,
        )
        return False

    def _validate_existing_collection(
        self,
        collection_name: str,
        expected_size: int,
        expected_distance: models.Distance,
    ) -> None:
        """
        Inspect an existing collection and verify configuration compatibility.

        Raises:
            CollectionConfigError: If vector dimension or distance metric mismatches.
        """
        try:
            info = self._client.get_collection(collection_name)
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Failed to retrieve metadata for existing collection '{collection_name}': {exc}"
            ) from exc

        vectors = info.config.params.vectors

        # Extract size and distance from VectorParams or dict
        if isinstance(vectors, models.VectorParams):
            actual_size = vectors.size
            actual_distance = vectors.distance
        elif isinstance(vectors, dict):
            first_vector = next(iter(vectors.values()))
            actual_size = getattr(first_vector, "size", None)
            actual_distance = getattr(first_vector, "distance", None)
        else:
            actual_size = getattr(vectors, "size", None)
            actual_distance = getattr(vectors, "distance", None)

        if actual_size != expected_size:
            raise CollectionConfigError(
                f"Collection '{collection_name}' vector dimension mismatch: "
                f"existing collection has size {actual_size}, but application requires {expected_size}. "
                f"Manual migration or recreation required."
            )

        # Normalize distance representation for comparison
        if actual_distance != expected_distance:
            raise CollectionConfigError(
                f"Collection '{collection_name}' distance metric mismatch: "
                f"existing collection has distance '{actual_distance}', but application requires '{expected_distance.value}'."
            )

        logger.debug(
            "Collection '%s' validated successfully (size=%d, distance=%s)",
            collection_name,
            actual_size,
            actual_distance,
        )

    def _create_payload_indexes(self, collection_name: str) -> None:
        """Create indexes on fields frequently used in metadata filtering."""
        import warnings

        indexed_fields = [
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("file_type", models.PayloadSchemaType.KEYWORD),
            ("source", models.PayloadSchemaType.KEYWORD),
        ]
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=".*Payload indexes have no effect in the local Qdrant.*"
            )
            for field_name, schema_type in indexed_fields:
                try:
                    self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=schema_type,
                    )
                    logger.debug(
                        "Created payload index for '%s' (%s) in '%s'",
                        field_name,
                        schema_type,
                        collection_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not create payload index for '%s' in '%s': %s",
                        field_name,
                        collection_name,
                        exc,
                    )

    # -----------------------------------------------------------------------
    # Vector Insertion & Idempotent Upsert
    # -----------------------------------------------------------------------

    def upsert_chunks(
        self,
        chunks: Sequence[Chunk],
        embeddings: Sequence[Union[list[float], EmbeddingResult]],
        batch_size: Optional[int] = None,
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Store chunks and corresponding embeddings in Qdrant with deterministic point IDs.

        Guarantees:
            - Strict 1-to-1 index alignment: chunk[i] is paired with embeddings[i].
            - Strict vector validation: dimension, numeric type, non-empty.
            - Idempotent upserts: same chunk produces the same deterministic UUID point ID.
            - Traceable payload: stores document provenance, chunk metadata, and chunk text.

        Args:
            chunks: Sequence of domain Chunk objects.
            embeddings: Sequence of float vectors or EmbeddingResult objects matching chunks.
            batch_size: Optional batch size override.
            collection_name: Optional collection name override.

        Returns:
            Number of points successfully upserted.

        Raises:
            VectorValidationError: If counts mismatch, vectors are malformed, or dimensions mismatch.
            VectorStoreError: If collection does not exist or upsert fails permanently.
        """
        if len(chunks) != len(embeddings):
            raise VectorValidationError(
                f"Count mismatch: chunks count ({len(chunks)}) does not match embeddings count ({len(embeddings)})."
            )

        if not chunks:
            return 0

        target_collection = collection_name or self.collection_name
        effective_batch_size = batch_size or self.batch_size

        points: list[models.PointStruct] = []

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            # Extract raw vector
            vector: list[float]
            if isinstance(emb, EmbeddingResult):
                vector = emb.embedding
            elif isinstance(emb, (list, tuple)):
                vector = list(emb)
            else:
                raise VectorValidationError(
                    f"Embedding at index {idx} must be a list of floats or EmbeddingResult, got {type(emb).__name__}."
                )

            # Validate vector
            self._validate_vector(vector, idx)

            # Generate deterministic UUID point ID
            point_id = generate_point_id(chunk.chunk_id)

            # Construct validated payload
            payload_model = build_payload_from_chunk(chunk)
            payload_dict = payload_model.model_dump()

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload_dict,
                )
            )

        # Upsert in batches with retry
        self._upsert_in_batches(
            points=points,
            batch_size=effective_batch_size,
            collection_name=target_collection,
        )

        return len(points)

    def upsert_points(
        self,
        points: Sequence[VectorPoint],
        batch_size: Optional[int] = None,
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Upsert pre-constructed VectorPoint instances into Qdrant.

        Args:
            points: Sequence of VectorPoint instances.
            batch_size: Optional batch size override.
            collection_name: Optional collection name override.

        Returns:
            Number of points upserted.
        """
        if not points:
            return 0

        target_collection = collection_name or self.collection_name
        effective_batch_size = batch_size or self.batch_size

        qdrant_points: list[models.PointStruct] = []
        for idx, pt in enumerate(points):
            self._validate_vector(pt.vector, idx)
            point_id = generate_point_id(pt.id)
            qdrant_points.append(
                models.PointStruct(
                    id=point_id,
                    vector=pt.vector,
                    payload=pt.payload,
                )
            )

        self._upsert_in_batches(
            points=qdrant_points,
            batch_size=effective_batch_size,
            collection_name=target_collection,
        )
        return len(points)

    def _validate_vector(self, vector: list[float], index: int) -> None:
        """
        Validate vector geometry, non-emptiness, numeric properties, and dimension.

        Raises:
            VectorValidationError: If validation fails.
        """
        if vector is None or not isinstance(vector, (list, tuple)):
            raise VectorValidationError(
                f"Vector at index {index} is missing or not a sequence."
            )

        if len(vector) == 0:
            raise VectorValidationError(f"Vector at index {index} is empty.")

        if len(vector) != self.vector_size:
            raise VectorValidationError(
                f"Vector at index {index} has dimension {len(vector)}, expected {self.vector_size}."
            )

        for elem_idx, val in enumerate(vector):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise VectorValidationError(
                    f"Vector at index {index} contains invalid non-finite value '{val}' at position {elem_idx}."
                )

    def _upsert_in_batches(
        self,
        points: list[models.PointStruct],
        batch_size: int,
        collection_name: str,
    ) -> None:
        """Slice points into batches and execute upsert with bounded retries."""
        total = len(points)
        for start_idx in range(0, total, batch_size):
            batch = points[start_idx : start_idx + batch_size]
            self._upsert_batch_with_retry(batch, collection_name)
            logger.debug(
                "Upserted batch [%d-%d/%d] points into '%s'",
                start_idx,
                start_idx + len(batch),
                total,
                collection_name,
            )

    def _upsert_batch_with_retry(
        self,
        batch: list[models.PointStruct],
        collection_name: str,
    ) -> None:
        """
        Execute a single batch upsert with bounded exponential backoff on transient errors.

        Raises:
            VectorStoreConnectionError: If network/connection failures exhaust retries.
            VectorStoreBatchError: If Qdrant returns a non-transient error (e.g. 400).
        """
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_retries:
            try:
                self._client.upsert(
                    collection_name=collection_name,
                    points=batch,
                )
                return
            except UnexpectedResponse as exc:
                # HTTP status errors from Qdrant REST API
                is_transient = exc.status_code >= 500 or exc.status_code in (408, 429)
                last_error = exc
                if not is_transient:
                    raise VectorStoreBatchError(
                        f"Qdrant rejected batch with status {exc.status_code}: {exc.content}"
                    ) from exc
            except (ResponseHandlingException, ConnectionError, OSError) as exc:
                # Connection / network level transient failure
                is_transient = True
                last_error = exc
            except Exception as exc:
                # Inspect for transient markers or re-raise
                err_str = str(exc).lower()
                is_transient = any(
                    marker in err_str
                    for marker in ("connection", "timeout", "unavailable", "reset", "refused")
                )
                last_error = exc
                if not is_transient:
                    raise VectorStoreBatchError(
                        f"Unexpected error during batch upsert to '{collection_name}': {exc}"
                    ) from exc

            if attempt < self.max_retries:
                attempt += 1
                delay = self.retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, _JITTER_MAX)
                logger.warning(
                    "Transient error during Qdrant upsert (attempt %d/%d): %s. Retrying in %.2fs...",
                    attempt,
                    self.max_retries,
                    last_error,
                    delay,
                )
                time.sleep(delay)
            else:
                break

        raise VectorStoreConnectionError(
            f"Failed to upsert batch to Qdrant collection '{collection_name}' after "
            f"{self.max_retries} retries. Last error: {last_error}"
        ) from last_error

    # -----------------------------------------------------------------------
    # Document Deletion (for safe re-ingestion)
    # -----------------------------------------------------------------------

    def delete_by_document_id(
        self,
        document_id: str,
        collection_name: Optional[str] = None,
    ) -> bool:
        """
        Delete all vector points belonging to a specific document_id.

        Used during document re-ingestion to eliminate stale chunks.

        Args:
            document_id: Unique document identifier.
            collection_name: Optional collection name override.

        Returns:
            True if deletion operation was executed successfully.

        Raises:
            VectorValidationError: If document_id is empty.
            VectorStoreError: If deletion fails.
        """
        if not document_id or not document_id.strip():
            raise VectorValidationError("document_id cannot be empty for deletion")

        target_name = collection_name or self.collection_name
        doc_filter = FilterBuilder.build(VectorStoreFilter(document_id=document_id.strip()))

        try:
            self._client.delete(
                collection_name=target_name,
                points_selector=models.FilterSelector(filter=doc_filter),
            )
            logger.info("Deleted chunks for document_id='%s' in '%s'", document_id, target_name)
            return True
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to delete points for document_id '{document_id}' in '{target_name}': {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Storage Inspection (Testing & Verification Helpers)
    # -----------------------------------------------------------------------

    def count(
        self,
        collection_name: Optional[str] = None,
        filter_spec: Optional[VectorStoreFilter] = None,
    ) -> int:
        """Return the count of points matching the optional filter in the collection."""
        target_name = collection_name or self.collection_name
        q_filter = FilterBuilder.build(filter_spec) if filter_spec else None
        res = self._client.count(
            collection_name=target_name,
            count_filter=q_filter,
            exact=True,
        )
        return res.count

    def get_point(
        self,
        point_id: str,
        collection_name: Optional[str] = None,
    ) -> Optional[models.Record]:
        """Retrieve a single point by ID (for inspection/testing)."""
        target_name = collection_name or self.collection_name
        resolved_id = generate_point_id(point_id)
        records = self._client.retrieve(
            collection_name=target_name,
            ids=[resolved_id],
            with_payload=True,
            with_vectors=True,
        )
        return records[0] if records else None
