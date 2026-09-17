"""
Deduplication utilities for retrieved candidate chunks.

Provides:
- Chunk-ID based deduplication (primary)
- Normalized content-based deduplication (secondary)
- Validation of candidate chunk fields
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Union

from app.retrieval.models import RetrievalResult
from app.reranking.models import RerankedResult

CandidateType = Union[RetrievalResult, RerankedResult]


def normalize_content_for_dedup(text: str) -> str:
    """
    Safely normalize text content for exact duplicate detection.

    Steps:
    1. Unicode NFKC normalization.
    2. Case folding (lowercase).
    3. Normalize all whitespace sequences (spaces, tabs, newlines) to a single space.
    4. Strip surrounding whitespace.

    Does not remove punctuation or perform aggressive stemming so that
    distinct evidence is never falsely collapsed.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    lowered = normalized.lower()
    collapsed = re.sub(r"\s+", " ", lowered)
    return collapsed.strip()


def is_valid_result(result: CandidateType) -> bool:
    """
    Verify whether a candidate result is structurally valid for context inclusion.

    Checks:
    - result is not None
    - chunk_id exists and is non-empty after stripping
    - content exists and is non-empty after stripping
    """
    if result is None:
        return False

    chunk_id = getattr(result, "chunk_id", None)
    if not chunk_id or not isinstance(chunk_id, str) or not chunk_id.strip():
        return False

    content = getattr(result, "content", None)
    if not content or not isinstance(content, str) or not content.strip():
        return False

    return True


def deduplicate_results(
    results: Sequence[CandidateType],
    deduplicate_content: bool = True,
) -> list[CandidateType]:
    """
    Filter duplicate and invalid candidates while strictly preserving rank order.

    Rules:
    1. Drop candidates failing `is_valid_result`.
    2. Primary deduplication: First occurrence of each `chunk_id` is retained;
       subsequent occurrences are discarded.
    3. Secondary deduplication (optional): If `deduplicate_content` is True,
       candidates with normalized content identical to a previously seen
       candidate are discarded.

    Args:
        results: Sequence of RetrievalResult or RerankedResult objects.
        deduplicate_content: If True, also filter by normalized content text.

    Returns:
        Deduplicated list preserving original input order.
    """
    deduped: list[CandidateType] = []
    seen_chunk_ids: set[str] = set()
    seen_contents: set[str] = set()

    for item in results:
        if not is_valid_result(item):
            continue

        chunk_id = item.chunk_id.strip()
        if chunk_id in seen_chunk_ids:
            continue

        if deduplicate_content:
            norm_content = normalize_content_for_dedup(item.content)
            if norm_content in seen_contents:
                continue
            seen_contents.add(norm_content)

        seen_chunk_ids.add(chunk_id)
        deduped.append(item)

    return deduped
