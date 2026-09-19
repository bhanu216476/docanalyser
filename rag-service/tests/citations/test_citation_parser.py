"""
Unit tests for CitationParser.

Verifies:
- Standard bracketed citation tags: [1], [2], [10].
- Multiple citations and grouped citations.
- Non-citation numbers are strictly ignored (12 days, 2026, Version 2).
- Malformed brackets are rejected ([], [abc], [-1], [0], [1.5]).
- Duplicate detection and order preservation.
"""

from __future__ import annotations

import pytest

from app.citations.parser import CitationParser


@pytest.fixture
def parser() -> CitationParser:
    return CitationParser()


class TestCitationParser:
    """Test suite for CitationParser."""

    def test_single_citation(self, parser: CitationParser) -> None:
        """Verify single bracketed citation tag is parsed."""
        text = "Employees receive 12 casual leave days [1]."
        ids = parser.parse(text)
        assert ids == [1]

    def test_multiple_citations_in_order(self, parser: CitationParser) -> None:
        """Verify multiple citations are extracted in exact appearance order."""
        text = "Casual leave is 12 days [1], and sick leave is 10 days [2]."
        ids = parser.parse(text)
        assert ids == [1, 2]

    def test_reverse_appearance_order(self, parser: CitationParser) -> None:
        """Verify citation order reflects appearance in text, not numeric sort."""
        text = "Sick leave is 10 days [2], whereas casual leave is 12 days [1]."
        ids = parser.parse(text)
        assert ids == [2, 1]

    def test_double_digit_citation(self, parser: CitationParser) -> None:
        """Verify IDs >= 10 are parsed correctly."""
        text = "According to Section 10 [10] and Appendix [12]."
        ids = parser.parse(text)
        assert ids == [10, 12]

    def test_consecutive_and_grouped_citations(self, parser: CitationParser) -> None:
        """Verify [1][2] and [1, 2] are correctly parsed."""
        text1 = "Both policies apply [1][2]."
        assert parser.parse(text1) == [1, 2]

        text2 = "Refer to guidelines [1, 2, 3]."
        assert parser.parse(text2) == [1, 2, 3]

    def test_duplicate_citations_preserved_in_parse(self, parser: CitationParser) -> None:
        """Verify parse() keeps repeated occurrences for duplicate analysis."""
        text = "Leave is 12 days [1]. The same rule applies to interns [1]."
        ids = parser.parse(text)
        assert ids == [1, 1]

    def test_parse_unique_deduplicates_in_first_appearance_order(
        self, parser: CitationParser
    ) -> None:
        """Verify parse_unique() returns deduplicated IDs in appearance order."""
        text = "Rule A [2], Rule B [1], and Rule C [2]."
        unique_ids = parser.parse_unique(text)
        assert unique_ids == [2, 1]

    def test_ordinary_numbers_not_matched(self, parser: CitationParser) -> None:
        """
        Verify ordinary numeric text is NEVER treated as citations.
        Examples: 12 days, 2026, Version 2, 100%, 3.14.
        """
        text = "In 2026, Version 2 of the 12 days policy was published with 100% compliance."
        ids = parser.parse(text)
        assert ids == []
        assert parser.has_citations(text) is False

    def test_malformed_bracketed_text_ignored(self, parser: CitationParser) -> None:
        """
        Verify non-integer or malformed brackets are rejected.
        [], [abc], [-1], [0], [1.5], [v1].
        """
        malformed = [
            "Empty brackets [] here",
            "Alphabetic tag [abc] here",
            "Version tag [v1] here",
            "Negative number [-1] here",
            "Zero index [0] here",
            "Floating point [1.5] here",
            "Special chars [@!#] here",
        ]
        for item in malformed:
            assert parser.parse(item) == [], f"Failed to reject: {item}"

    def test_empty_or_none_text(self, parser: CitationParser) -> None:
        """Verify empty or None inputs return empty list."""
        assert parser.parse("") == []
        assert parser.parse("   ") == []
        assert parser.parse(None) == []  # type: ignore[arg-type]
        assert parser.has_citations("") is False

    def test_parse_spans(self, parser: CitationParser) -> None:
        """Verify parse_spans provides exact character offsets and raw tags."""
        text = "Policy note [1] and rule [2]."
        spans = parser.parse_spans(text)
        assert len(spans) == 2

        assert spans[0].citation_id == 1
        assert spans[0].raw_tag == "[1]"
        assert text[spans[0].start : spans[0].end] == "[1]"

        assert spans[1].citation_id == 2
        assert spans[1].raw_tag == "[2]"
        assert text[spans[1].start : spans[1].end] == "[2]"
