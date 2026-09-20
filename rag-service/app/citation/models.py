"""Models for citation extraction."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ExtractedCitations(BaseModel):
    """Canonical citation references extracted from a generated answer."""

    citations: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
