"""Models returned by the evidence decision layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DecisionResult(BaseModel):
    """Decision about whether the retrieved evidence supports generation."""

    should_answer: bool
    reason: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)