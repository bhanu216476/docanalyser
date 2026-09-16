"""Pydantic models for deterministic, citation-aware evidence context."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ContextItem(BaseModel):
    """One reranked evidence chunk prepared for downstream generation."""

    position: int = Field(..., ge=1, description="1-based context position.")
    chunk_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    document_id: str = ""
    file_name: str = ""
    page_numbers: list[int] = Field(default_factory=list)
    section: str | None = None
    source: str = ""
    citation: str = Field(..., min_length=1)
    reranked_rank: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(frozen=True)

    @field_validator("chunk_id", "content")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        """Reject identifiers and evidence that contain no usable text."""

        if not value.strip():
            raise ValueError("value cannot be blank")
        return value

    @field_validator("page_numbers")
    @classmethod
    def validate_page_numbers(cls, value: list[int]) -> list[int]:
        """Require canonical page numbers to be positive integers."""

        if any(page < 1 for page in value):
            raise ValueError("page numbers must be positive")
        return value


class StructuredContext(BaseModel):
    """Ordered evidence and its prompt-ready representation."""

    items: list[ContextItem] = Field(default_factory=list)
    formatted_text: str = ""

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def item_count(self) -> int:
        """Return the number of evidence items in the context."""

        return len(self.items)