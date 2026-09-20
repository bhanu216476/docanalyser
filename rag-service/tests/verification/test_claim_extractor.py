"""
Unit tests for ClaimExtractor.

Tests:
- Single cited claim extraction
- Multiple cited claims in one answer
- Uncited claims (no citation markers)
- Mixed cited and uncited
- Empty / blank answer
- Citation markers stripped from claim text
- Answer with only citation markers and no factual text
- Sentence splitting edge cases
"""

from __future__ import annotations

import pytest
from app.verification.claim_extractor import ClaimExtractor
from app.verification.models import Claim


@pytest.fixture
def extractor() -> ClaimExtractor:
    return ClaimExtractor()


class TestClaimExtractorSingleClaim:
    """Single claim extraction."""

    def test_single_cited_claim(self, extractor: ClaimExtractor) -> None:
        answer = "Employees receive 12 casual leave days [1]."
        claims = extractor.extract(answer)
        assert len(claims) == 1
        c = claims[0]
        assert c.claim_id == 1
        assert "12 casual leave days" in c.text
        assert "[1]" not in c.text  # citation marker stripped
        assert c.citation_ids == [1]

    def test_single_uncited_claim(self, extractor: ClaimExtractor) -> None:
        answer = "Employees receive 12 casual leave days."
        claims = extractor.extract(answer)
        assert len(claims) == 1
        c = claims[0]
        assert c.citation_ids == []  # UNCITED
        assert "12 casual leave days" in c.text

    def test_claim_text_has_no_brackets(self, extractor: ClaimExtractor) -> None:
        answer = "Leave must be approved by the manager [1]."
        claims = extractor.extract(answer)
        assert len(claims) == 1
        assert "[" not in claims[0].text
        assert "]" not in claims[0].text


class TestClaimExtractorMultipleClaims:
    """Multiple claims in one answer."""

    def test_two_cited_claims(self, extractor: ClaimExtractor) -> None:
        answer = (
            "Employees receive 12 casual leave days [1]. "
            "Leave requests must be submitted through the HR portal [2]."
        )
        claims = extractor.extract(answer)
        assert len(claims) == 2
        assert claims[0].citation_ids == [1]
        assert claims[1].citation_ids == [2]

    def test_three_mixed_claims(self, extractor: ClaimExtractor) -> None:
        answer = (
            "Employees receive 12 casual leave days [1]. "
            "Annual leave is 20 days. "
            "HR portal approval is required [2]."
        )
        claims = extractor.extract(answer)
        assert len(claims) == 3
        cited_claims = [c for c in claims if c.citation_ids]
        uncited_claims = [c for c in claims if not c.citation_ids]
        assert len(cited_claims) == 2
        assert len(uncited_claims) == 1

    def test_claim_ids_are_sequential(self, extractor: ClaimExtractor) -> None:
        answer = "Claim one [1]. Claim two [2]. Claim three [3]."
        claims = extractor.extract(answer)
        assert len(claims) == 3
        for i, c in enumerate(claims, start=1):
            assert c.claim_id == i


class TestClaimExtractorMultiCitationClaim:
    """Claims with multiple citation IDs."""

    def test_multi_citation_claim(self, extractor: ClaimExtractor) -> None:
        answer = "Employees receive 12 casual leave days and 15 sick leave days [1][2]."
        claims = extractor.extract(answer)
        assert len(claims) == 1
        assert set(claims[0].citation_ids) == {1, 2}

    def test_comma_separated_citations(self, extractor: ClaimExtractor) -> None:
        answer = "Leave must be approved [1, 2]."
        claims = extractor.extract(answer)
        assert len(claims) == 1
        assert set(claims[0].citation_ids) == {1, 2}


class TestClaimExtractorEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_answer(self, extractor: ClaimExtractor) -> None:
        assert extractor.extract("") == []
        assert extractor.extract("   ") == []

    def test_none_like_blank(self, extractor: ClaimExtractor) -> None:
        assert extractor.extract("") == []

    def test_only_citation_markers(self, extractor: ClaimExtractor) -> None:
        # "[1]" alone after stripping leaves nothing factual
        claims = extractor.extract("[1].")
        # Either empty or filtered — must not claim meaningful text
        for c in claims:
            assert c.text.strip() not in ("", "[1]")

    def test_citation_ids_deduplicated_per_claim(self, extractor: ClaimExtractor) -> None:
        answer = "The policy states [1] this is true [1]."
        claims = extractor.extract(answer)
        # Claim should only contain unique IDs
        if claims:
            for c in claims:
                assert len(c.citation_ids) == len(set(c.citation_ids))

    def test_long_answer_preserves_order(self, extractor: ClaimExtractor) -> None:
        sentences = [f"Statement number {i} is valid [{i}]." for i in range(1, 6)]
        answer = " ".join(sentences)
        claims = extractor.extract(answer)
        assert len(claims) == 5
        for i, c in enumerate(claims, start=1):
            assert c.claim_id == i
            assert i in c.citation_ids
