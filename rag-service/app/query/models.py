"""
Domain models for Advanced Query Intelligence in DocAnalyser RAG Platform.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class QueryIntent(str, Enum):
    """Semantic intent classification of the user's input."""

    FACTUAL = "FACTUAL"              # Specific lookup, definitions, exact values
    CONCEPTUAL = "CONCEPTUAL"        # Explanations, mechanisms, architecture
    COMPARISON = "COMPARISON"        # Contrast/comparison between entities or docs
    SUMMARY = "SUMMARY"              # Executive summary, overview, bullet points
    EXPLORATION = "EXPLORATION"      # Quiz generation, comprehension questions, study notes
    CONVERSATIONAL = "CONVERSATIONAL" # Greetings, chitchat, non-document questions
    MULTI_PART = "MULTI_PART"        # Composite questions requiring decomposition
    UNKNOWN = "UNKNOWN"


class QuerySubGoal(BaseModel):
    """Decomposed sub-query goal for multi-part questions."""

    subquery: str = Field(..., description="Actionable subquery text.")
    intent: QueryIntent = Field(default=QueryIntent.FACTUAL)
    weight: float = Field(default=1.0, ge=0.0, le=2.0)
    target_document_id: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


class QueryAnalysis(BaseModel):
    """Complete intelligence analysis of an incoming user query."""

    original_query: str = Field(..., description="Raw user query text.")
    intent: QueryIntent = Field(default=QueryIntent.FACTUAL)
    rewritten_query: str = Field(..., description="Context-resolved search query.")
    subqueries: list[str] = Field(default_factory=list, description="Decomposed subqueries if composite.")
    expanded_terms: list[str] = Field(default_factory=list, description="Synonyms and related search terms.")
    detected_entities: list[str] = Field(default_factory=list, description="Named entities or technical terms.")
    is_follow_up: bool = Field(default=False, description="True if query resolves context from history.")
    requires_retrieval: bool = Field(default=True, description="False if query is casual greeting/chitchat.")
    recommended_top_k: int = Field(default=5, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
