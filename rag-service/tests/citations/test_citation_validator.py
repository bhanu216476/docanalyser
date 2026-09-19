"""
Unit tests for CitationValidator.

Verifies:
- Valid citations matching the registry pass validation.
- Invalid / unknown citation IDs are detected and reported.
- Duplicate citation references are tracked.
- Policy enforcement: WARN records warnings, REJECT raises InvalidCitationError.
- Empty registry and empty answer scenarios.
"""

from __future__ import annotations

import pytest

from app.context.models import Citation
from app.citations.models import (
    CitationValidationPolicy,
    CitationValidationResult,
    InvalidCitationError,
)
from app.citations.validator import CitationValidator


@pytest.fixture
def sample_registry() -> dict[int, Citation]:
    """Sample authoritative citation registry with IDs 1, 2, 3."""
    return {
        1: Citation(
            id=1,
            citation_id="[1]",
            chunk_id="chunk-1",
            file_name="leave_policy.pdf",
            page_number=4,
        ),
        2: Citation(
            id=2,
            citation_id="[2]",
            chunk_id="chunk-2",
            file_name="leave_policy.pdf",
            page_number=5,
        ),
        3: Citation(
            id=3,
            citation_id="[3]",
            chunk_id="chunk-3",
            file_name="employee_handbook.pdf",
            page_number=10,
        ),
    }


class TestCitationValidator:
    """Test suite for CitationValidator."""

    def test_all_valid_citations(self, sample_registry: dict[int, Citation]) -> None:
        """Verify validation passes when all citations exist in the registry."""
        validator = CitationValidator()
        result: CitationValidationResult = validator.validate(
            parsed_ids=[1, 2],
            registry=sample_registry,
        )
        assert result.valid is True
        assert result.citation_ids == [1, 2]
        assert result.invalid_ids == []
        assert result.duplicates == []
        assert result.warnings == []

    def test_invalid_citation_detected_warn_policy(
        self, sample_registry: dict[int, Citation]
    ) -> None:
        """Verify invalid citation [4] is detected under default WARN policy."""
        validator = CitationValidator(default_policy=CitationValidationPolicy.WARN)
        result: CitationValidationResult = validator.validate(
            parsed_ids=[1, 4],
            registry=sample_registry,
        )
        assert result.valid is False
        assert result.citation_ids == [1, 4]
        assert result.invalid_ids == [4]
        assert len(result.warnings) > 0
        assert "[4]" in result.warnings[0]

    def test_invalid_citation_reject_policy_raises(
        self, sample_registry: dict[int, Citation]
    ) -> None:
        """Verify REJECT policy raises InvalidCitationError on unknown citation IDs."""
        validator = CitationValidator(default_policy=CitationValidationPolicy.REJECT)
        with pytest.raises(InvalidCitationError) as exc_info:
            validator.validate(
                parsed_ids=[1, 99],
                registry=sample_registry,
            )
        assert exc_info.value.invalid_ids == [99]

    def test_duplicate_citations_recorded(
        self, sample_registry: dict[int, Citation]
    ) -> None:
        """Verify duplicate references are detected and listed in duplicates."""
        validator = CitationValidator()
        result = validator.validate(
            parsed_ids=[1, 2, 1, 1],
            registry=sample_registry,
        )
        assert result.valid is True
        assert result.citation_ids == [1, 2]
        assert result.duplicates == [1]
        assert len(result.warnings) == 1
        assert "[1]" in result.warnings[0]

    def test_empty_registry_with_citations(self) -> None:
        """Verify all citations are invalid when registry is empty."""
        validator = CitationValidator()
        result = validator.validate(
            parsed_ids=[1, 2],
            registry={},
        )
        assert result.valid is False
        assert result.invalid_ids == [1, 2]

    def test_empty_parsed_ids(self, sample_registry: dict[int, Citation]) -> None:
        """Verify empty citation list returns valid=True with no errors."""
        validator = CitationValidator()
        result = validator.validate(
            parsed_ids=[],
            registry=sample_registry,
        )
        assert result.valid is True
        assert result.citation_ids == []
        assert result.invalid_ids == []
        assert result.duplicates == []
        assert result.warnings == []

    def test_string_keys_in_registry_supported(self) -> None:
        """Verify registry keyed by '[1]' or '1' is supported seamlessly."""
        str_registry = {
            "[1]": Citation(citation_id="[1]", chunk_id="c1", file_name="doc.pdf"),
            "[2]": Citation(citation_id="[2]", chunk_id="c2", file_name="doc.pdf"),
        }
        validator = CitationValidator()
        result = validator.validate([1, 2], str_registry)
        assert result.valid is True
        assert result.invalid_ids == []
