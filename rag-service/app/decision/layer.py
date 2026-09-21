"""Deterministic evidence sufficiency policy."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.context.models import BuiltContext
from app.decision.models import DecisionResult

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_NON_INFORMATIVE_TOKENS = {
    "about",
    "after",
    "are",
    "can",
    "does",
    "for",
    "from",
    "how",
    "into",
    "many",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


class DecisionLayer:
    """Decide whether selected context is meaningfully related to a query.

    Retrieval scores are intentionally not thresholded here because the project
    supports score types with incompatible scales. The post-context lexical
    overlap check is deterministic and uses only evidence that would otherwise
    be sent to the LLM.
    """

    def evaluate(self, query: str, context: BuiltContext) -> DecisionResult:
        """Return a generation decision for the built evidence context."""
        if not context.selected_chunks:
            return DecisionResult(
                should_answer=False,
                reason="no_selected_chunks",
                confidence=0.0,
            )

        evidence_tokens = self._tokens(
            chunk.content for chunk in context.selected_chunks
        )
        if not context.context_text.strip() or not evidence_tokens:
            return DecisionResult(
                should_answer=False,
                reason="empty_evidence",
                confidence=0.0,
            )

        query_tokens = self._tokens([query])
        if not query_tokens:
            return DecisionResult(
                should_answer=False,
                reason="empty_query_terms",
                confidence=0.0,
            )

        overlap = query_tokens & evidence_tokens
        if not overlap:
            return DecisionResult(
                should_answer=False,
                reason="irrelevant_evidence",
                confidence=0.0,
            )

        confidence = len(overlap) / len(query_tokens)
        return DecisionResult(
            should_answer=True,
            reason="sufficient_evidence",
            confidence=confidence,
        )

    @staticmethod
    def _tokens(values: Iterable[str]) -> set[str]:
        return {
            token
            for value in values
            for token in _TOKEN_PATTERN.findall(value.lower())
            if token not in _NON_INFORMATIVE_TOKENS and len(token) > 2
        }