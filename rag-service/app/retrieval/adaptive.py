"""
Adaptive Hybrid Retrieval Enhancements for DocAnalyser RAG Platform.
Implements:
- Multi-query candidate fusion
- Semantic chunk deduplication (Jaccard token similarity)
- Score normalization across heterogeneous retrieval distances
- Low-relevance noise filtering
- Dynamic top-K calibration
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Sequence
from typing import Any

from app.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


def normalize_dense_score(score: float) -> float:
    """Normalize cosine similarity from [-1, 1] to [0, 1]."""
    if math.isnan(score):
        return 0.0
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def normalize_bm25_score(score: float, max_score: float | None = None) -> float:
    """Normalize BM25 unbounded positive score to [0, 1] using soft sigmoid."""
    if score <= 0.0 or math.isnan(score):
        return 0.0
    if max_score and max_score > 0.0:
        return min(1.0, score / max_score)
    # Sigmoidal scaling for BM25 scores (scores typically range 0 to ~30)
    return 1.0 - (1.0 / (1.0 + (score / 8.0)))


def compute_token_jaccard(text_a: str, text_b: str) -> float:
    """Calculate token-level Jaccard overlap similarity between two text chunks."""
    tokens_a = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text_a.lower()))
    tokens_b = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def deduplicate_chunks(
    candidates: Sequence[RetrievalResult],
    similarity_threshold: float = 0.75,
) -> list[RetrievalResult]:
    """
    Eliminate redundant overlapping chunks from the candidate pool.

    Preserves the higher-ranked chunk and discards near-duplicate text
    from the same or related documents to maximize context diversity.

    Args:
        candidates: Ranked list of retrieval results.
        similarity_threshold: Jaccard overlap threshold above which chunk is dropped.

    Returns:
        Deduplicated list of RetrievalResult objects.
    """
    if not candidates:
        return []

    unique_results: list[RetrievalResult] = []
    seen_chunk_ids: set[str] = set()

    for candidate in candidates:
        if candidate.chunk_id in seen_chunk_ids:
            continue

        # Check overlap against already accepted candidates
        is_duplicate = False
        cand_doc = candidate.document_id or candidate.metadata.get("document_id")

        for accepted in unique_results:
            acc_doc = accepted.document_id or accepted.metadata.get("document_id")
            # If from the same document and content overlap exceeds threshold
            if cand_doc and acc_doc and cand_doc == acc_doc:
                jaccard = compute_token_jaccard(candidate.content, accepted.content)
                if jaccard >= similarity_threshold:
                    logger.debug(
                        "Deduplicating chunk '%s' (Jaccard %.2f with '%s')",
                        candidate.chunk_id,
                        jaccard,
                        accepted.chunk_id,
                    )
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique_results.append(candidate)
            seen_chunk_ids.add(candidate.chunk_id)

    logger.debug(
        "Deduplication: reduced %d candidates to %d unique chunks",
        len(candidates),
        len(unique_results),
    )
    return unique_results


def filter_by_relevance_floor(
    candidates: Sequence[RetrievalResult],
    min_score_percentile: float = 0.15,
    min_results: int = 3,
) -> list[RetrievalResult]:
    """
    Filter out distant noise chunks that fall far below the top candidate's score.

    Ensures at least min_results are preserved when available.
    """
    if len(candidates) <= min_results:
        return list(candidates)

    scores = [c.score for c in candidates if not math.isnan(c.score)]
    if not scores:
        return list(candidates)

    max_s = max(scores)
    # If scores are non-positive (e.g. negated distances), preserve all
    if max_s <= 0.0:
        return list(candidates)

    cutoff = max_s * min_score_percentile
    filtered = [c for c in candidates if c.score >= cutoff]

    # Ensure we retain at least min_results if available
    if len(filtered) < min_results:
        return list(candidates[:min_results])

    return filtered


def merge_subquery_results(
    subquery_result_lists: Sequence[Sequence[RetrievalResult]],
    top_k: int = 10,
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    """
    Fuse multiple retrieval results from decomposed subqueries into a single ranked pool.

    Uses Reciprocal Rank Fusion across all subquery result sets.
    """
    if not subquery_result_lists:
        return []
    if len(subquery_result_lists) == 1:
        return list(subquery_result_lists[0][:top_k])

    from app.retrieval.fusion import reciprocal_rank_fusion

    fused = reciprocal_rank_fusion(
        ranked_lists=subquery_result_lists,
        rrf_k=rrf_k,
        top_k=top_k * 2,
    )
    # Deduplicate overlapping chunks across the subqueries
    deduped = deduplicate_chunks(fused, similarity_threshold=0.75)
    return deduped[:top_k]
