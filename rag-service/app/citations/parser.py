"""
Citation parser for extracting bracketed evidence citations from generated answers.

Extracts [1], [2], [10], etc., while ignoring ordinary numbers (e.g., "12 days", "2026", "Version 2").
Preserves exact appearance order and records duplicate references.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional


class CitationSpan(NamedTuple):
    """Details of a parsed citation reference in source text."""

    citation_id: int
    raw_tag: str
    start: int
    end: int


class CitationParser:
    """
    Parser for extracting grounded citation identifiers from LLM output.

    Supported patterns:
        - Single bracketed integers: "[1]", "[2]", "[10]"
        - Multi-citation bracketed groups: "[1, 2]", "[1, 3, 5]"
        - Consecutive brackets: "[1][2]"

    Non-citations strictly ignored:
        - Unbracketed numbers: "12 days", "2026", "Version 2"
        - Non-integer tags: "[v1]", "[abc]", "[section 2]"
        - Floats and decimals: "[1.5]", "[3.14]"
        - Negative or zero values: "[-1]", "[0]"
        - Empty brackets: "[]"
    """

    # Matches bracketed sequences of positive integers separated by commas
    _CITATION_GROUP_PATTERN = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")

    def parse(self, text: Optional[str]) -> list[int]:
        """
        Extract all citation integer IDs in order of appearance.

        Duplicates are preserved in the returned list so that downstream
        validators can detect and report duplicate citation references.

        Args:
            text: Generated answer text.

        Returns:
            List of 1-based integer citation IDs (e.g. [1, 2, 1]).
        """
        if not text or not isinstance(text, str):
            return []

        citation_ids: list[int] = []
        for match in self._CITATION_GROUP_PATTERN.finditer(text):
            inner_content = match.group(1)
            parts = [p.strip() for p in inner_content.split(",") if p.strip()]
            for part in parts:
                try:
                    val = int(part)
                    # Grounded citations are 1-based positive integers
                    if val >= 1:
                        citation_ids.append(val)
                except ValueError:
                    continue

        return citation_ids

    def parse_unique(self, text: Optional[str]) -> list[int]:
        """
        Extract unique citation IDs, strictly preserving order of first appearance.

        Args:
            text: Generated answer text.

        Returns:
            Deduplicated list of integer citation IDs in order of first appearance.
        """
        all_ids = self.parse(text)
        seen: set[int] = set()
        unique_ids: list[int] = []
        for cid in all_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)
        return unique_ids

    def parse_spans(self, text: Optional[str]) -> list[CitationSpan]:
        """
        Extract detailed span information for each valid citation reference.

        Args:
            text: Generated answer text.

        Returns:
            List of CitationSpan objects detailing ID, raw tag, and char offsets.
        """
        if not text or not isinstance(text, str):
            return []

        spans: list[CitationSpan] = []
        for match in self._CITATION_GROUP_PATTERN.finditer(text):
            raw_tag = match.group(0)
            inner_content = match.group(1)
            parts = [p.strip() for p in inner_content.split(",") if p.strip()]
            for part in parts:
                try:
                    val = int(part)
                    if val >= 1:
                        spans.append(
                            CitationSpan(
                                citation_id=val,
                                raw_tag=raw_tag,
                                start=match.start(),
                                end=match.end(),
                            )
                        )
                except ValueError:
                    continue
        return spans

    def has_citations(self, text: Optional[str]) -> bool:
        """Return True if text contains at least one valid citation identifier."""
        return len(self.parse(text)) > 0
