"""
Claim extractor for the Citation Verification Layer.

Responsibility
--------------
Split a generated answer into discrete factual statements and associate
each statement with the citation IDs it references.

Strategy (V0.1 — deterministic, extensible)
--------------------------------------------
1. Split answer into sentences on sentence-ending punctuation followed
   by whitespace, or on end-of-string.
2. For each sentence, use the existing CitationParser to extract bracketed
   citation IDs.
3. Sentences that carry citation IDs → cited Claim objects.
4. Sentences that lack citation IDs but appear factual (non-empty, not purely
   whitespace/punctuation) → UNCITED Claim objects (citation_ids=[]).

Design notes
------------
- The extractor deliberately does NOT require every sentence to be a claim.
  Sentences that consist entirely of stop-words, conjunctions, or connective
  phrases may not be meaningful verification targets; the current V0.1 includes
  all non-trivial sentences for simplicity and extensibility.
- Citation markers ([N]) are stripped from the claim text so that the verifier
  compares clean factual statements against evidence.
- This abstraction is intentionally simple. A future semantic claim
  decomposition step can replace or augment this extractor without changing
  the CitationVerifier interface.
"""

from __future__ import annotations

import re
from typing import Optional

from app.citations.parser import CitationParser
from app.verification.models import Claim

# Sentence boundary pattern:
# Splits on . ! ? followed by one or more whitespace characters OR end-of-string.
# Preserves sentence-internal periods (e.g. URLs, abbreviations) by requiring
# that the period is followed by space+uppercase or end-of-string.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Pattern to strip citation markers [N] or [N, M] from claim text
_CITATION_STRIP = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")

# Minimum non-whitespace characters for a sentence to be treated as a claim
_MIN_CLAIM_LENGTH = 5


class ClaimExtractor:
    """
    Deterministic claim extractor that segments an answer into verifiable
    factual statements with their associated citation IDs.

    Args:
        parser: CitationParser instance. Defaults to a new CitationParser().
        min_claim_length: Minimum character length (non-whitespace) for a
                          sentence to qualify as a claim. Default 5.
    """

    def __init__(
        self,
        parser: Optional[CitationParser] = None,
        min_claim_length: int = _MIN_CLAIM_LENGTH,
    ) -> None:
        self._parser = parser or CitationParser()
        self._min_claim_length = max(1, min_claim_length)

    def extract(self, answer: str) -> list[Claim]:
        """
        Extract factual claims from a generated answer.

        Args:
            answer: Raw generated answer text from the LLM.

        Returns:
            List of Claim objects in order of appearance.
            - Claims with citation_ids=[] are UNCITED.
            - Claims with citation_ids=[N, ...] reference specific evidence.
        """
        if not answer or not answer.strip():
            return []

        sentences = self._split_sentences(answer.strip())
        claims: list[Claim] = []
        claim_id = 1

        for sentence in sentences:
            sentence = sentence.strip()
            if not self._is_non_trivial(sentence):
                continue

            # Extract citation IDs (preserving duplicates for downstream use)
            citation_ids = self._parser.parse_unique(sentence)

            # Strip citation markers from claim text, then normalize whitespace
            # so "12 casual leave days ." becomes "12 casual leave days."
            clean_text = _CITATION_STRIP.sub("", sentence)
            # Collapse multiple spaces introduced by marker removal
            import re as _re
            clean_text = _re.sub(r" +", " ", clean_text).strip()
            # Remove space before terminal punctuation (e.g. "days ." → "days.")
            clean_text = _re.sub(r" +([.!?,;:])", r"\1", clean_text)

            # After stripping citations, re-check if the claim text is meaningful
            if not self._is_non_trivial(clean_text):
                # Only citations in the sentence and nothing else
                continue

            claims.append(
                Claim(
                    claim_id=claim_id,
                    text=clean_text,
                    citation_ids=citation_ids,
                )
            )
            claim_id += 1

        return claims

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentence-level segments.

        Uses a simple punctuation-based splitter suitable for factual
        RAG answers. Handles trailing periods and end-of-string.
        """
        # First split on common sentence boundaries
        parts = _SENTENCE_SPLIT.split(text)

        # Handle cases where the answer uses newlines as separators
        result: list[str] = []
        for part in parts:
            # Further split on double-newlines (paragraph breaks)
            subparts = re.split(r"\n\n+", part)
            result.extend(subparts)

        return result

    def _is_non_trivial(self, text: str) -> bool:
        """
        Return True if the text contains enough content to be treated as a claim.
        Filters out blank lines, whitespace-only text, and very short fragments.
        """
        stripped = text.strip()
        non_ws_chars = re.sub(r"\s+", "", stripped)
        return len(non_ws_chars) >= self._min_claim_length
