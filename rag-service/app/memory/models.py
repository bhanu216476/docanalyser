"""
Data models for Token-Aware Conversational Memory in DocAnalyser.
"""

from __future__ import annotations

import time
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConversationTurn(BaseModel):
    """Single turn in a conversational session."""

    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'.")
    content: str = Field(..., description="Message text.")
    timestamp: float = Field(default_factory=time.time)
    token_count: int = Field(default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ConversationMemoryState(BaseModel):
    """Structured state of a multi-turn conversation session."""

    session_id: str = Field(..., description="Unique conversation session identifier.")
    summary: str | None = Field(default=None, description="Distilled summary of older truncated turns.")
    turns: list[ConversationTurn] = Field(default_factory=list, description="Active recent conversational turns.")
    total_tokens: int = Field(default=0)
    document_scope: list[str] = Field(default_factory=list, description="Active document IDs for this session.")

    model_config = ConfigDict(frozen=True)
