"""
Citation validator for verifying citations against an authoritative registry.

Enforces citation integrity:
- Verifies every cited ID resolves against the registry.
- Detects invalid/unknown IDs and warns or rejects per policy.
- Identifies duplicate citation references.
- Never allows fabricated source metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Union

from app.context.models import Citation
from app.citations.models import (
    CitationValidationPolicy,
    CitationValidationResult,
    InvalidCitationError,
)

logger = logging.getLogger(__name__)

RegistryType = Mapping[Union[int, str], Any]


class CitationValidator:
    """
    Validates parsed citation IDs against the authoritative Citation Registry.

    Responsibilities:
    1. Check presence of each parsed ID in the registry.
    2. Collect invalid (unregistered) citation IDs.
    3. Collect duplicate citation references.
    4. Enforce configured CitationValidationPolicy (WARN vs REJECT).
    5. Return typed CitationValidationResult.
    """

    def __init__(
        self,
        default_policy: CitationValidationPolicy = CitationValidationPolicy.WARN,
    ) -> None:
        self.default_policy = default_policy

    def validate(
        self,
        parsed_ids: list[int],
        registry: RegistryType,
        policy: Optional[CitationValidationPolicy] = None,
    ) -> CitationValidationResult:
        """
        Validate a list of parsed citation IDs against the citation registry.

        Args:
            parsed_ids: Sequential list of parsed integer IDs from the answer (including duplicates).
            registry: Authoritative citation registry mapping integer (or string) IDs to Citations.
            policy: Enforcement policy override (WARN or REJECT).

        Returns:
            CitationValidationResult with validation status, IDs, invalid IDs, duplicates, and warnings.

        Raises:
            InvalidCitationError: If policy is REJECT and any invalid citation IDs are present.
        """
        enforce_policy = policy or self.default_policy

        # Normalize registry keys to integers for fast, consistent O(1) membership checks
        normalized_keys: set[int] = set()
        for k in registry.keys():
            if isinstance(k, int):
                normalized_keys.add(k)
            elif isinstance(k, str):
                digits = "".join(filter(str.isdigit, k))
                if digits:
                    normalized_keys.add(int(digits))

        unique_ids: list[int] = []
        duplicates: list[int] = []
        invalid_ids: list[int] = []
        warnings: list[str] = []

        seen: set[int] = set()
        seen_duplicates: set[int] = set()

        for cid in parsed_ids:
            if cid in seen:
                if cid not in seen_duplicates:
                    duplicates.append(cid)
                    seen_duplicates.add(cid)
            else:
                seen.add(cid)
                unique_ids.append(cid)
                if cid not in normalized_keys:
                    invalid_ids.append(cid)

        is_valid = len(invalid_ids) == 0

        # Construct diagnostic warnings
        if invalid_ids:
            warning_msg = (
                f"Generated answer contains invalid citation IDs not in registry: "
                f"{[f'[{x}]' for x in invalid_ids]}. "
                f"Available registry IDs: {[f'[{x}]' for x in sorted(normalized_keys)]}."
            )
            warnings.append(warning_msg)
            logger.warning("Citation validation failure: %s", warning_msg)

        if duplicates:
            dup_msg = (
                f"Citation IDs referenced multiple times: {[f'[{x}]' for x in duplicates]}."
            )
            warnings.append(dup_msg)

        # Policy enforcement
        if not is_valid and enforce_policy == CitationValidationPolicy.REJECT:
            raise InvalidCitationError(
                invalid_ids=invalid_ids,
                message=f"Citation validation rejected: invalid IDs {[f'[{x}]' for x in invalid_ids]}",
            )

        return CitationValidationResult(
            valid=is_valid,
            citation_ids=unique_ids,
            invalid_ids=invalid_ids,
            duplicates=duplicates,
            warnings=warnings,
        )
