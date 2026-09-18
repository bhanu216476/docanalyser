"""Provider-independent models for answer generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.context.models import StructuredContext


class GenerationRequest(BaseModel):
    query: str = Field(..., min_length=1)
    context: StructuredContext

    model_config = ConfigDict(frozen=True)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be empty or whitespace-only")
        return value


class GeneratedAnswer(BaseModel):
    answer: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(frozen=True)

    @field_validator("answer", "model")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value cannot be empty or whitespace-only")
        return value