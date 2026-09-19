"""
Citation mapper service for mapping LLM answer citations back to authoritative source metadata.

Flow:
    Generated Answer Text
           ↓
    Citation Parser (extract [1], [2], ...)
           ↓
    Citation Validator (verify IDs against registry, detect duplicates/unknowns)
           ↓
    Citation Registry Lookup (O(1) authoritative metadata resolution)
           ↓
    Deduplicated Structured Citations (preserving first appearance order)
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Union

from app.context.models import Citation
from app.citations.models import (
    CitationValidationPolicy,
    CitationValidationResult,
    GroundedCitation,
)
from app.citations.parser import CitationParser
from app.citations.validator import CitationValidator

logger = logging.getLogger(__name__)

# Markers indicating that the LLM explicitly refused or lacked information to answer
INSUFFICIENT_INFORMATION_MARKERS = (
    "not contain sufficient information",
    "insufficient information",
    "cannot find",
    "not mentioned",
    "no information",
    "unsupported",
    "provided sources do not",
    "cannot be determined from the provided",
    "do not contain enough information",
    "not available in the provided sources",
)


class CitationMapper:
    """
    Service responsible for parsing, validating, and resolving citations
    from generated answers against the authoritative Context Builder citation registry.

    Guarantees:
        1. Authoritative metadata: Source document, page, and chunk metadata are
           ALWAYS resolved from the registry. Generated LLM text is NEVER trusted for metadata.
        2. First appearance ordering: Citations are ordered by their first occurrence in the answer.
        3. Deterministic deduplication: Repeated references (e.g. [1] ... [1]) yield a single citation.
        4. Strict page integrity: Missing page metadata remains None; page 1 is never invented.
        5. Refusal safety: No-answer or refusal responses produce an empty citations list [].
        6. Raw answer preservation: Answer text is passed through unchanged.
    """

    def __init__(
        self,
        parser: Optional[CitationParser] = None,
        validator: Optional[CitationValidator] = None,
        default_policy: CitationValidationPolicy = CitationValidationPolicy.WARN,
    ) -> None:
        self.parser = parser or CitationParser()
        self.validator = validator or CitationValidator(default_policy=default_policy)
        self.default_policy = default_policy

    def is_refusal_or_unsupported(self, answer: str) -> bool:
        """
        Detect if an answer explicitly expresses a refusal or lack of supporting evidence.
        """
        if not answer:
            return True
        lower_ans = answer.lower()
        return any(marker in lower_ans for marker in INSUFFICIENT_INFORMATION_MARKERS)

    def map_citations(
        self,
        answer: str,
        registry: Mapping[Union[int, str], Citation],
        policy: Optional[CitationValidationPolicy] = None,
    ) -> tuple[list[GroundedCitation], CitationValidationResult]:
        """
        Parse, validate, and map citation IDs in answer text to GroundedCitation models.

        Args:
            answer: Raw text response from LLM.
            registry: Authoritative citation registry from Context Builder.
            policy: Enforcement policy (WARN or REJECT). Defaults to self.default_policy.

        Returns:
            Tuple of:
                - List of GroundedCitation objects (in order of first appearance, deduplicated).
                - CitationValidationResult containing validation diagnostics.
        """
        # Step 1: Check for explicit refusal or insufficient information
        if self.is_refusal_or_unsupported(answer):
            validation = CitationValidationResult(
                valid=True,
                citation_ids=[],
                invalid_ids=[],
                duplicates=[],
                warnings=[],
            )
            return [], validation

        # Step 2: Parse all bracketed citation IDs from answer (preserves duplicates for validation)
        parsed_ids = self.parser.parse(answer)

        # Step 3: Validate parsed IDs against registry
        validation = self.validator.validate(
            parsed_ids=parsed_ids,
            registry=registry,
            policy=policy or self.default_policy,
        )

        # Build normalized int -> Citation lookup table
        normalized_registry: dict[int, Citation] = {}
        for k, v in registry.items():
            if isinstance(k, int):
                normalized_registry[k] = v
            elif isinstance(k, str):
                digits = "".join(filter(str.isdigit, k))
                if digits:
                    normalized_registry[int(digits)] = v

        # Step 4: Resolve valid citations preserving first appearance order (deduplicated)
        grounded_citations: list[GroundedCitation] = []
        for cid in validation.citation_ids:
            if cid in normalized_registry:
                source_citation = normalized_registry[cid]
                grounded = GroundedCitation.from_citation(
                    citation=source_citation,
                    id_override=cid,
                )
                grounded_citations.append(grounded)

        return grounded_citations, validation

    def map_to_context_citations(
        self,
        answer: str,
        registry: Mapping[Union[int, str], Citation],
        policy: Optional[CitationValidationPolicy] = None,
    ) -> tuple[list[Citation], CitationValidationResult]:
        """
        Convenience method that returns existing Context Citation objects
        (with id and document fields populated) for direct pipeline backward compatibility.
        """
        grounded_list, validation = self.map_citations(
            answer=answer,
            registry=registry,
            policy=policy,
        )

        normalized_registry: dict[int, Citation] = {}
        for k, v in registry.items():
            if isinstance(k, int):
                normalized_registry[k] = v
            elif isinstance(k, str):
                digits = "".join(filter(str.isdigit, k))
                if digits:
                    normalized_registry[int(digits)] = v

        context_citations: list[Citation] = []
        for grounded in grounded_list:
            if grounded.id in normalized_registry:
                cit = normalized_registry[grounded.id]
                context_citations.append(cit)

        return context_citations, validation
