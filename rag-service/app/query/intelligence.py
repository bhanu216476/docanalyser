"""
Unified Query Intelligence Service for DocAnalyser RAG Platform.
Coordinates query intent classification, contextual reference resolution,
multi-part decomposition, and dynamic retrieval parameter recommendation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.query.classifier import QueryIntentClassifier
from app.query.models import QueryAnalysis, QueryIntent
from app.query.rewriter import QueryRewriter

logger = logging.getLogger(__name__)


class QueryIntelligenceService:
    """Orchestrates query understanding, intent classification, and rewriting."""

    def __init__(
        self,
        classifier: QueryIntentClassifier | None = None,
        rewriter: QueryRewriter | None = None,
    ) -> None:
        self.classifier = classifier or QueryIntentClassifier()
        self.rewriter = rewriter or QueryRewriter()

    def analyze(
        self,
        query: str,
        conversation_history: list[dict[str, str]] | None = None,
        has_document_filters: bool = False,
    ) -> QueryAnalysis:
        """
        Execute comprehensive intelligence analysis on a user query.

        Args:
            query: Raw user query string.
            conversation_history: List of recent user/assistant turns.
            has_document_filters: True if the user is scoped to specific documents.

        Returns:
            Validated QueryAnalysis instance with intent, rewritten query,
            decomposed subqueries, and retrieval recommendations.
        """
        clean_query = query.strip()
        if not clean_query:
            return QueryAnalysis(
                original_query=query,
                intent=QueryIntent.CONVERSATIONAL,
                rewritten_query=query,
                requires_retrieval=False,
                recommended_top_k=3,
            )

        # 1. Intent Classification
        intent = self.classifier.classify(clean_query, has_document_filters=has_document_filters)

        # 2. Conversational bypass: greetings and casual chitchat do not require document retrieval
        if intent == QueryIntent.CONVERSATIONAL and not has_document_filters:
            return QueryAnalysis(
                original_query=clean_query,
                intent=intent,
                rewritten_query=clean_query,
                subqueries=[clean_query],
                requires_retrieval=False,
                recommended_top_k=3,
            )

        # 3. Contextual reference resolution (pronouns, ordinal referents)
        rewritten_query, is_follow_up, entities = self.rewriter.rewrite_with_context(
            clean_query, conversation_history
        )

        # 4. Multi-part query decomposition
        subqueries = self.rewriter.decompose(rewritten_query, intent)

        # 5. Technical synonym and keyword expansion
        expanded_terms = self.rewriter.expand_terms(rewritten_query)

        # 6. Dynamic Top-K recommendation based on query complexity
        recommended_top_k = self._recommend_top_k(intent, len(subqueries))

        return QueryAnalysis(
            original_query=clean_query,
            intent=intent,
            rewritten_query=rewritten_query,
            subqueries=subqueries,
            expanded_terms=expanded_terms,
            detected_entities=entities,
            is_follow_up=is_follow_up,
            requires_retrieval=True,
            recommended_top_k=recommended_top_k,
            metadata={
                "subquery_count": len(subqueries),
                "has_expansion": bool(expanded_terms),
            },
        )

    @staticmethod
    def _recommend_top_k(intent: QueryIntent, subquery_count: int) -> int:
        """Dynamically calibrate top-K retrieval budget to query intent."""
        if subquery_count > 1 or intent in (QueryIntent.COMPARISON, QueryIntent.MULTI_PART):
            return 8
        if intent == QueryIntent.SUMMARY:
            return 7
        if intent in (QueryIntent.CONCEPTUAL, QueryIntent.EXPLORATION):
            return 6
        return 5
