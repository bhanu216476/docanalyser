"""
Context-Aware Query Rewriting, Decomposition, and Expansion for DocAnalyser RAG Platform.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from app.query.models import QueryIntent

logger = logging.getLogger(__name__)

# Common synonyms and domain expansion mapping
DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "architecture": ["system design", "components", "infrastructure", "pipeline"],
    "rag": ["retrieval augmented generation", "hybrid retrieval", "vector search"],
    "database": ["datastore", "postgres", "postgresql", "persistence", "storage"],
    "vectordb": ["vector database", "qdrant", "vector store", "embeddings"],
    "cache": ["redis", "in-memory cache", "session store"],
    "auth": ["authentication", "jwt", "authorization", "token", "security"],
    "latency": ["response time", "execution time", "performance", "throughput"],
    "accuracy": ["precision", "groundedness", "faithfulness", "relevance"],
    "citation": ["source attribution", "evidence", "provenance", "reference"],
    "comparison": ["differences", "pros and cons", "trade-offs", "contrasting"],
    "ingestion": ["document processing", "chunking", "parsing", "indexing"],
}

PRONOUN_TRIGGERS: frozenset[str] = frozenset({
    "it", "its", "they", "them", "their", "that", "this", "these", "those",
    "the former", "the latter", "the first one", "the second one", "the third one",
    "previous one", "another one", "same", "such",
})

FOLLOW_UP_ACTION_TRIGGERS: frozenset[str] = frozenset({
    "explain more", "tell me more", "expand on", "elaborate on",
    "why", "how so", "what else", "give details", "more details",
    "what about", "and about", "in detail",
})


class QueryRewriter:
    """Handles query resolution, multi-part decomposition, and term expansion."""

    def is_follow_up(self, query: str) -> bool:
        """Check if query is dependent on preceding conversational context."""
        q_lower = query.strip().lower()
        words = set(re.findall(r"\b[a-z0-9'-]+\b", q_lower))

        if words & PRONOUN_TRIGGERS:
            return True

        if any(trigger in q_lower for trigger in FOLLOW_UP_ACTION_TRIGGERS):
            return True

        # Very short queries (1-3 words) like "and advantages?" or "how?"
        if len(q_lower.split()) <= 3 and not q_lower.startswith(("what is", "define", "who is")):
            return True

        return False

    def rewrite_with_context(
        self,
        query: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> tuple[str, bool, list[str]]:
        """
        Resolve anaphoric pronouns and follow-up context using conversational memory.

        Returns:
            (rewritten_query, is_follow_up, extracted_entities)
        """
        if not conversation_history:
            return query, False, []

        if not self.is_follow_up(query):
            # Query is already specific and self-contained; do not alter
            return query, False, self._extract_key_phrases(query)

        # Extract recent user queries and assistant responses
        recent_turns: list[dict[str, str]] = [
            turn for turn in conversation_history[-6:]
            if isinstance(turn, dict) and turn.get("content", "").strip()
        ]

        if not recent_turns:
            return query, False, []

        # Find the primary subject / entities from the most recent user turn or assistant turn
        last_user_query = ""
        for turn in reversed(recent_turns):
            if turn.get("role") == "user":
                last_user_query = turn.get("content", "").strip()
                break

        last_assistant_answer = ""
        for turn in reversed(recent_turns):
            if turn.get("role") == "assistant":
                last_assistant_answer = turn.get("content", "").strip()
                break

        # Extract subject from previous user query
        subject = self._extract_subject_from_query(last_user_query)

        # If subject not evident from user query, extract prominent capitalized or technical terms from assistant turn
        if not subject and last_assistant_answer:
            subject = self._extract_subject_from_text(last_assistant_answer)

        if not subject:
            return query, True, []

        q_lower = query.lower()

        # Handle ordinal resolution like "explain the second one", "what about the first?"
        ordinal_match = re.search(r"\b(first|second|third|fourth|fifth)\s+(one|point|advantage|reason|feature|item)\b", q_lower)
        if ordinal_match and last_assistant_answer:
            ordinal_word = ordinal_match.group(1)
            target_item = self._extract_numbered_item(last_assistant_answer, ordinal_word)
            if target_item:
                rewritten = f"{subject} {target_item}: {query}"
                logger.info("Ordinal follow-up rewritten from '%s' to '%s'", query, rewritten)
                return rewritten, True, [subject, target_item]

        # Pronoun replacement
        rewritten = query
        for pronoun in ["its", "it", "their", "they", "that", "this"]:
            pattern = re.compile(rf"\b{pronoun}\b", re.IGNORECASE)
            if pattern.search(rewritten):
                if pronoun in ("its", "their"):
                    replacement = f"{subject}'s"
                else:
                    replacement = subject
                rewritten = pattern.sub(replacement, rewritten, count=1)
                break

        # If query is a concise follow-up like "and advantages?" or "elaborate"
        if subject.lower() not in rewritten.lower():
            rewritten = f"{subject} {rewritten}"

        logger.info("Contextual query resolved from '%s' to '%s'", query, rewritten)
        return rewritten, True, [subject]

    def decompose(self, query: str, intent: QueryIntent) -> list[str]:
        """
        Decompose complex multi-part queries into standalone search goals.

        Example:
            "Explain the architecture of this system and compare it with the previous version."
            -> ["architecture of this system", "compare system with previous version"]
        """
        if intent not in (QueryIntent.MULTI_PART, QueryIntent.COMPARISON):
            return [query]

        # Split on coordinating conjunctions with questions or 'and compare'
        split_patterns = [
            r"\s+and\s+(?:also\s+)?(?:compare\s+(?:it\s+)?with|contrast\s+(?:it\s+)?with)\s+",
            r"\s+and\s+(?:also\s+)?(?:explain|describe|detail|how\s+does)\s+",
            r"\?\s+(?:and\s+)?",
            r";\s*",
        ]

        for pat in split_patterns:
            parts = re.split(pat, query, flags=re.IGNORECASE)
            if len(parts) >= 2:
                subqueries = [p.strip(" ?.!") for p in parts if p.strip()]
                if len(subqueries) >= 2:
                    logger.info("Decomposed query '%s' into %d subqueries: %s", query, len(subqueries), subqueries)
                    return subqueries

        return [query]

    def expand_terms(self, query: str) -> list[str]:
        """
        Expand technical terms with high-relevance domain synonyms.
        """
        expanded: list[str] = []
        q_lower = query.lower()
        for term, synonyms in DOMAIN_SYNONYMS.items():
            if re.search(rf"\b{term}\b", q_lower):
                for syn in synonyms:
                    if syn.lower() not in q_lower and syn not in expanded:
                        expanded.append(syn)
        return expanded[:4]

    # --- Private Helpers ---

    @staticmethod
    def _extract_subject_from_query(query: str) -> str:
        """Strip introductory interrogatives to isolate the core noun phrase."""
        clean = re.sub(
            r"^(what\s+is|what\s+are|how\s+does|explain|tell\s+me\s+about|describe|why\s+is|define)\s+",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip(" ?.,!")
        return clean.strip()

    @staticmethod
    def _extract_subject_from_text(text: str) -> str:
        """Find the main entity or leading topic from assistant output."""
        # Find first markdown bold title like **PostgreSQL** or leading sentence subject
        match = re.search(r"\*\*([a-zA-Z0-9_\-\s]{2,30})\*\*", text)
        if match:
            return match.group(1).strip()
        first_line = text.split("\n")[0]
        words = first_line.split()[:4]
        return " ".join(words).strip(" #*:")

    @staticmethod
    def _extract_numbered_item(text: str, ordinal: str) -> str | None:
        """Extract specific numbered item from list (e.g. 'second' -> item 2)."""
        ordinal_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        idx = ordinal_map.get(ordinal.lower(), 1)
        # Search for numbered list lines like "1. ...", "2. ...", "2) ..."
        pattern = re.compile(rf"(?:^|\n)\s*{idx}[\.\)]\s*([^\n\r]+)", re.MULTILINE)
        match = pattern.search(text)
        if match:
            item_text = match.group(1).strip()
            # Return first phrase before colon or dash
            clean_item = re.split(r"[:\-\–]", item_text)[0].strip(" *")
            return clean_item
        return None

    @staticmethod
    def _extract_key_phrases(query: str) -> list[str]:
        """Extract significant technical terms."""
        words = re.findall(r"\b[A-Z][a-zA-Z0-9_]+\b|\b[a-zA-Z0-9_]{4,}\b", query)
        stopwords = {"what", "when", "where", "which", "with", "from", "that", "this", "have", "been"}
        return [w for w in words if w.lower() not in stopwords][:5]
