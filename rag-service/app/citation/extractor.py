"""Citation marker extraction from generated answers."""

from __future__ import annotations

import re

from app.citation.models import ExtractedCitations


class CitationExtractor:
    """Extract canonical [n] citation markers from generated answers."""

    _CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    def extract(self, answer: str) -> ExtractedCitations:
        """Extract unique positive citation numbers in first-seen order."""
        seen: set[int] = set()
        citations: list[int] = []

        for match in self._CITATION_PATTERN.finditer(answer):
            citation_number = int(match.group(1))

            if citation_number <= 0 or citation_number in seen:
                continue

            seen.add(citation_number)
            citations.append(citation_number)

        return ExtractedCitations(citations=citations)
