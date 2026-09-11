"""
Qdrant vector storage module.

Provides a clean abstraction for vector persistence, collection management,
payload validation, and metadata filtering.
"""

from __future__ import annotations

from app.vector_store.exceptions import (
    CollectionConfigError,
    FilterValidationError,
    VectorStoreBatchError,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorValidationError,
)
from app.vector_store.filters import (
    ALLOWED_FILTER_FIELDS,
    FilterBuilder,
    VectorStoreFilter,
)
from app.vector_store.models import (
    DOCANALYSER_NAMESPACE,
    VectorPayload,
    VectorPoint,
    build_payload_from_chunk,
    generate_point_id,
)
from app.vector_store.qdrant_client import create_qdrant_client
from app.vector_store.qdrant_store import QdrantVectorStore

__all__ = [
    # Main store & client
    "QdrantVectorStore",
    "create_qdrant_client",
    # Models
    "VectorPoint",
    "VectorPayload",
    "generate_point_id",
    "build_payload_from_chunk",
    "DOCANALYSER_NAMESPACE",
    # Filters
    "VectorStoreFilter",
    "FilterBuilder",
    "ALLOWED_FILTER_FIELDS",
    # Exceptions
    "VectorStoreError",
    "VectorStoreConnectionError",
    "CollectionConfigError",
    "VectorValidationError",
    "FilterValidationError",
    "VectorStoreBatchError",
]
