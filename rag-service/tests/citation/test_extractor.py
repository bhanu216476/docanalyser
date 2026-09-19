"""Tests for citation marker extraction."""

from __future__ import annotations

from app.citation.extractor import CitationExtractor


def test_extracts_basic_citation() -> None:
    result = CitationExtractor().extract("Machine learning is useful [1].")

    assert result.citations == [1]


def test_extracts_multiple_citations() -> None:
    result = CitationExtractor().extract("ML [1] and DL [2] are related [3].")

    assert result.citations == [1, 2, 3]


def test_removes_duplicate_citations_preserving_first_seen_order() -> None:
    result = CitationExtractor().extract(
        "This is supported [2]. Another statement [1]. Again [2]."
    )

    assert result.citations == [2, 1]


def test_extracts_adjacent_citations() -> None:
    result = CitationExtractor().extract("The result is supported [1][2].")

    assert result.citations == [1, 2]


def test_extracts_multi_digit_citations() -> None:
    result = CitationExtractor().extract("[10] [25] [100]")

    assert result.citations == [10, 25, 100]


def test_ignores_invalid_citations() -> None:
    result = CitationExtractor().extract("[abc] [x] []")

    assert result.citations == []


def test_ignores_zero_citation() -> None:
    result = CitationExtractor().extract("[0]")

    assert result.citations == []


def test_returns_empty_list_when_no_citations_exist() -> None:
    result = CitationExtractor().extract("This answer contains no citation markers.")

    assert result.citations == []


def test_extracts_only_valid_markers_inside_normal_text() -> None:
    result = CitationExtractor().extract(
        "Text [12] includes [abc], [3x], and [4]valid markers."
    )

    assert result.citations == [12, 4]


def test_extraction_is_deterministic() -> None:
    extractor = CitationExtractor()
    answer = "Evidence [3], [1], [3], and [20]."

    first = extractor.extract(answer)
    second = extractor.extract(answer)

    assert first == second
    assert first.citations == [3, 1, 20]


def test_handles_whitespace_and_punctuation_around_citations() -> None:
    result = CitationExtractor().extract(
        "Start: [1], middle ([2]); end [3]!\nNext line [4]."
    )

    assert result.citations == [1, 2, 3, 4]