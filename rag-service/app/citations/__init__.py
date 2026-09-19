"""
Citation Mapping and Validation Package.

Provides reliable parsing, validation, and mapping of citation IDs from LLM-generated answers
back to authoritative evidence and source metadata produced by the Context Builder.
"""

from app.citations.models import (
    CitationValidationPolicy,
    CitationValidationResult,
    GroundedCitation,
    InvalidCitationError,
)
from app.citations.parser import CitationParser, CitationSpan
from app.citations.validator import CitationValidator
from app.citations.mapper import CitationMapper

__all__ = [
    "CitationValidationPolicy",
    "CitationValidationResult",
    "GroundedCitation",
    "InvalidCitationError",
    "CitationParser",
    "CitationSpan",
    "CitationValidator",
    "CitationMapper",
]
