"""
Deterministic query intent classification for DocAnalyser RAG Platform.
Provides zero-overhead, high-precision intent classification without unnecessary LLM latency.
"""

from __future__ import annotations

import re
from app.query.models import QueryIntent


class QueryIntentClassifier:
    """Classifies user queries into semantic retrieval intents."""

    # Pre-compiled regex patterns for intent detection
    _GREETING_REGEX = re.compile(
        r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy|sup)(\s+.*)?$",
        re.IGNORECASE,
    )
    _CASUAL_REGEX = re.compile(
        r"^(who\s+are\s+you|what\s+is\s+your\s+name|how\s+are\s+you|thanks|thank\s+you|bye|goodbye|cool|awesome|nice|ok|okay|got\s+it)[\.!\?]*$",
        re.IGNORECASE,
    )
    _COMPARISON_REGEX = re.compile(
        r"\b(compare|comparison|versus|vs\.?|difference\s+between|differences|differs?|similarities|similar\s+to|trade-?offs?|pros\s+and\s+cons|better\s+than|advantages\s+and\s+disadvantages)\b",
        re.IGNORECASE,
    )
    _SUMMARY_REGEX = re.compile(
        r"\b(summar(y|ize|ization)|overview|tldr|tl;dr|recap|abstract|brief\s+summary|key\s+takeaways|high-level\s+overview|main\s+points)\b",
        re.IGNORECASE,
    )
    _EXPLORATION_REGEX = re.compile(
        r"\b(generate\s+\d*\s*questions?|quiz|test\s+comprehension|sample\s+questions|flashcards?|practice\s+questions?|study\s+guide|practice\s+exam)\b",
        re.IGNORECASE,
    )
    _MULTI_PART_REGEX = re.compile(
        r"(\band\s+(also\s+)?(compare|explain|what\s+about|describe|how\s+does)\b|\?.*\?|\balso\s+(tell|give|list)\b)",
        re.IGNORECASE,
    )
    _CONCEPTUAL_REGEX = re.compile(
        r"\b(how\s+does|explain|architecture|mechanism|workflow|pipeline|under\s+the\s+hood|in-depth|design\s+of|rationale)\b",
        re.IGNORECASE,
    )

    def classify(self, query: str, has_document_filters: bool = False) -> QueryIntent:
        """
        Classify the intent of the incoming query.

        Args:
            query: User's raw question string.
            has_document_filters: Whether a specific document filter is currently active.

        Returns:
            QueryIntent enumeration.
        """
        text = query.strip()
        if not text:
            return QueryIntent.CONVERSATIONAL

        # 1. Check for casual / conversational greetings first (unless explicitly attached to a document query)
        if not has_document_filters:
            if self._GREETING_REGEX.match(text) or self._CASUAL_REGEX.match(text):
                return QueryIntent.CONVERSATIONAL

        # 2. Check for multi-part composite questions
        if self._MULTI_PART_REGEX.search(text) and len(text.split()) >= 6:
            return QueryIntent.MULTI_PART

        # 3. Check for comparisons
        if self._COMPARISON_REGEX.search(text):
            return QueryIntent.COMPARISON

        # 4. Check for exploration / quizzes
        if self._EXPLORATION_REGEX.search(text):
            return QueryIntent.EXPLORATION

        # 5. Check for summaries
        if self._SUMMARY_REGEX.search(text):
            return QueryIntent.SUMMARY

        # 6. Check for deep conceptual explanations
        if self._CONCEPTUAL_REGEX.search(text):
            return QueryIntent.CONCEPTUAL

        # 7. Default to factual query lookup
        return QueryIntent.FACTUAL
