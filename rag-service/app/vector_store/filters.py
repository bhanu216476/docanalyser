"""
Metadata filter models and builder for Qdrant vector storage.

Provides a clean, validated abstraction for constructing native Qdrant filter
queries without writing raw JSON or string dictionaries.

Supported filterable fields:
    - document_id (string or list of strings)
    - file_type (string or list of strings)
    - source (string)
    - chunk_index (integer)
    - file_name (string)
    - section (string)

Strictly validates field names against an authorized whitelist to prevent
un-indexed or arbitrary injection into vector store queries.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import models

from app.vector_store.exceptions import FilterValidationError

# Whitelist of approved filterable fields aligned with payload schema and payload indexes
ALLOWED_FILTER_FIELDS: frozenset[str] = frozenset(
    {
        "document_id",
        "file_type",
        "source",
        "chunk_index",
        "file_name",
        "section",
    }
)


class VectorStoreFilter(BaseModel):
    """
    Controlled filter specification for vector store operations.

    All attributes are optional. Multiple conditions are combined with logical AND (must).

    Attributes:
        document_id:    Filter by one or more document IDs.
        file_type:      Filter by one or more file types (e.g. 'md', 'txt').
        source:         Filter by exact normalized source URI/path.
        chunk_index:    Filter by exact 0-based chunk index.
        file_name:      Filter by source file name.
        section:        Filter by Markdown section title.
        custom_filters: Additional key-value filters. Keys must be in ``ALLOWED_FILTER_FIELDS``.
    """

    document_id: Optional[str | list[str]] = Field(
        default=None,
        description="Filter by single document ID or list of document IDs.",
    )
    file_type: Optional[str | list[str]] = Field(
        default=None,
        description="Filter by single file type or list of file types.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by exact source path.",
    )
    chunk_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Filter by chunk index.",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="Filter by source file name.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Filter by section title.",
    )
    custom_filters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional key-value conditions. Keys must be in ALLOWED_FILTER_FIELDS.",
    )

    model_config = ConfigDict(frozen=True)


class FilterBuilder:
    """
    Constructs and validates native Qdrant `models.Filter` objects.
    """

    @classmethod
    def validate_field_name(cls, field_name: str) -> None:
        """
        Ensure field name is in the allowed whitelist.

        Raises:
            FilterValidationError: If field_name is not allowed.
        """
        if field_name not in ALLOWED_FILTER_FIELDS:
            allowed_list = sorted(list(ALLOWED_FILTER_FIELDS))
            raise FilterValidationError(
                f"Invalid filter field '{field_name}'. "
                f"Allowed filter fields are: {allowed_list}"
            )

    @classmethod
    def build(
        cls,
        filter_spec: VectorStoreFilter | dict[str, Any] | None = None,
    ) -> models.Filter | None:
        """
        Convert a VectorStoreFilter or dictionary into a native Qdrant `models.Filter`.

        Args:
            filter_spec: VectorStoreFilter instance or dict of field conditions.

        Returns:
            Native `models.Filter` instance, or `None` if no filter criteria specified.

        Raises:
            FilterValidationError: If any field name is invalid or unapproved.
        """
        if filter_spec is None:
            return None

        if isinstance(filter_spec, dict):
            # Validate dict keys
            for key in filter_spec:
                cls.validate_field_name(key)
            filter_obj = VectorStoreFilter(
                document_id=filter_spec.get("document_id"),
                file_type=filter_spec.get("file_type"),
                source=filter_spec.get("source"),
                chunk_index=filter_spec.get("chunk_index"),
                file_name=filter_spec.get("file_name"),
                section=filter_spec.get("section"),
                custom_filters={
                    k: v
                    for k, v in filter_spec.items()
                    if k not in {
                        "document_id",
                        "file_type",
                        "source",
                        "chunk_index",
                        "file_name",
                        "section",
                    }
                } or None,
            )
        else:
            filter_obj = filter_spec

        # Check custom filters keys
        if filter_obj.custom_filters:
            for key in filter_obj.custom_filters:
                cls.validate_field_name(key)

        must_conditions: list[models.FieldCondition] = []

        # Document ID filter
        if filter_obj.document_id is not None:
            must_conditions.append(cls._build_match_condition("document_id", filter_obj.document_id))

        # File type filter
        if filter_obj.file_type is not None:
            must_conditions.append(cls._build_match_condition("file_type", filter_obj.file_type))

        # Source filter
        if filter_obj.source is not None:
            must_conditions.append(cls._build_match_condition("source", filter_obj.source))

        # Chunk index filter
        if filter_obj.chunk_index is not None:
            must_conditions.append(cls._build_match_condition("chunk_index", filter_obj.chunk_index))

        # File name filter
        if filter_obj.file_name is not None:
            must_conditions.append(cls._build_match_condition("file_name", filter_obj.file_name))

        # Section filter
        if filter_obj.section is not None:
            must_conditions.append(cls._build_match_condition("section", filter_obj.section))

        # Custom filters
        if filter_obj.custom_filters:
            for key, val in filter_obj.custom_filters.items():
                must_conditions.append(cls._build_match_condition(key, val))

        if not must_conditions:
            return None

        return models.Filter(must=must_conditions)

    @classmethod
    def build_or(
        cls,
        filters: Sequence[VectorStoreFilter | dict[str, Any]],
    ) -> models.Filter | None:
        """
        Combine multiple filter specifications with logical OR (should).

        Args:
            filters: Sequence of VectorStoreFilter or dict filter objects.

        Returns:
            Native `models.Filter` with `should` conditions.
        """
        should_filters: list[models.Filter] = []
        for f in filters:
            q_filter = cls.build(f)
            if q_filter is not None:
                should_filters.append(q_filter)

        if not should_filters:
            return None

        return models.Filter(should=should_filters)

    @staticmethod
    def _build_match_condition(field: str, value: Any) -> models.FieldCondition:
        """Construct a Qdrant FieldCondition using MatchValue or MatchAny."""
        if isinstance(value, (list, tuple, set)):
            return models.FieldCondition(
                key=field,
                match=models.MatchAny(any=list(value)),
            )
        return models.FieldCondition(
            key=field,
            match=models.MatchValue(value=value),
        )
