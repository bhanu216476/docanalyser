"""Validated models returned by dense retrieval."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrievalResult(BaseModel):
    """A ranked result that preserves the source embedded chunk."""

    chunk_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float
    rank: int = Field(..., ge=1)

    model_config = ConfigDict(frozen=True)

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        """Reject non-finite similarity scores."""
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value
