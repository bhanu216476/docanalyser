"""
Context Builder module.

Transforms raw or reranked retrieval candidates into structured, token-budgeted,
citation-linked evidence blocks for LLM prompt injection.
"""

from app.context.models import (
    BuiltContext,
    Citation,
    ContextBuilderConfig,
    ContextChunk,
)
from app.context.token_budget import (
    BudgetTracker,
    DeterministicCharRatioTokenCounter,
    TiktokenCounter,
    TokenCounter,
    WhitespaceTokenCounter,
)
from app.context.citation import extract_citation, format_citation_id
from app.context.deduplicator import deduplicate_results, is_valid_result, normalize_content_for_dedup
from app.context.context_builder import ContextBuilder, format_context_block

__all__ = [
    "BuiltContext",
    "Citation",
    "ContextBuilder",
    "ContextBuilderConfig",
    "ContextChunk",
    "TokenCounter",
    "TiktokenCounter",
    "WhitespaceTokenCounter",
    "DeterministicCharRatioTokenCounter",
    "BudgetTracker",
    "extract_citation",
    "format_citation_id",
    "deduplicate_results",
    "is_valid_result",
    "normalize_content_for_dedup",
    "format_context_block",
]
