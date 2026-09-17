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
from app.context.models import ContextItem, StructuredContext

# --------------------------------------------------------------------------
# Full context-builder models and utilities (BuiltContext-based).
# --------------------------------------------------------------------------
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
from app.context.deduplicator import (
    deduplicate_results,
    is_valid_result,
    normalize_content_for_dedup,
)
from app.context.context_builder import format_context_block

__all__ = [
    # origin/main backward-compatible exports
    "ContextBuilder",
    "ContextItem",
    "StructuredContext",
    # full context-builder models
    "BuiltContext",
    "Citation",
    "ContextBuilderConfig",
    "ContextChunk",
    # token counting
    "TokenCounter",
    "TiktokenCounter",
    "WhitespaceTokenCounter",
    "DeterministicCharRatioTokenCounter",
    "BudgetTracker",
    # citation helpers
    "extract_citation",
    "format_citation_id",
    # deduplication helpers
    "deduplicate_results",
    "is_valid_result",
    "normalize_content_for_dedup",
    # formatting
    "format_context_block",
]
