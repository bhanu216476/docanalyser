"""Tests for citation extraction models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.citation.models import ExtractedCitations


def test_accepts_citation_list() -> None:
    citations = ExtractedCitations(citations=[1, 2, 10])

    assert citations.citations == [1, 2, 10]


def test_citations_default_to_empty_list() -> None:
    assert ExtractedCitations().citations == []


def test_citations_reject_negative_values() -> None:
    with pytest.raises(ValidationError):
        ExtractedCitations(citations=[-1])


def test_citations_model_is_frozen() -> None:
    citations = ExtractedCitations(citations=[1])

    with pytest.raises(Exception):
        citations.citations = [2]  # type: ignore[misc]