"""
Context module.

Provides both the lightweight structured context builder (origin/main, StructuredContext)
and the full token-budgeted context builder (feature/context-builder, BuiltContext).
"""

# --------------------------------------------------------------------------
# Lightweight builder from origin/main (StructuredContext-based).
# Imported by tests/context/test_builder.py.
# --------------------------------------------------------------------------
from app.context.builder import ContextBuilder
from app.context.citation import extract_citation, format_citation_id
from app.context.context_builder import format_context_block
from app.context.deduplicator import (
    deduplicate_results,
    is_valid_result,
    normalize_content_for_dedup,
)

# --------------------------------------------------------------------------
# Full context-builder models and utilities (BuiltContext-based).
# --------------------------------------------------------------------------
from app.context.models import (
    BuiltContext,
    Citation,
    ContextBuilderConfig,
    ContextChunk,
    ContextItem,
    StructuredContext,
)
from app.context.token_budget import (
    BudgetTracker,
    DeterministicCharRatioTokenCounter,
    TiktokenCounter,
    TokenCounter,
    WhitespaceTokenCounter,
)

__all__ = [
    "BudgetTracker",
    # full context-builder models
    "BuiltContext",
    "Citation",
    # origin/main backward-compatible exports
    "ContextBuilder",
    "ContextBuilderConfig",
    "ContextChunk",
    "ContextItem",
    "DeterministicCharRatioTokenCounter",
    "StructuredContext",
    "TiktokenCounter",
    # token counting
    "TokenCounter",
    "WhitespaceTokenCounter",
    # deduplication helpers
    "deduplicate_results",
    # citation helpers
    "extract_citation",
    "format_citation_id",
    # formatting
    "format_context_block",
    "is_valid_result",
    "normalize_content_for_dedup",
]
