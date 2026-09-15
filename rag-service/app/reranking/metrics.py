"""
Ranking change metrics computation.

Provides a single import for all mathematical metrics comparing
pre-reranking candidate sets to post-reranking result sets.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Optional

from app.retrieval.models import RetrievalResult
from app.reranking.models import RankingChangeMetrics, RerankedResult


def _spearman_correlation(rank_a: list[int], rank_b: list[int]) -> Optional[float]:
    """
    Compute Spearman rank correlation between two equal-length rank lists.

    Returns None if fewer than 2 paired elements exist.
    """
    n = len(rank_a)
    if n < 2:
        return None

    mean_a = sum(rank_a) / n
    mean_b = sum(rank_b) / n

    num = sum((a - mean_a) * (b - mean_b) for a, b in zip(rank_a, rank_b))
    denom_a = math.sqrt(sum((a - mean_a) ** 2 for a in rank_a))
    denom_b = math.sqrt(sum((b - mean_b) ** 2 for b in rank_b))

    if denom_a == 0.0 or denom_b == 0.0:
        return None

    return num / (denom_a * denom_b)


def compute_ranking_metrics(
    candidates: Sequence[RetrievalResult],
    reranked: Sequence[RerankedResult],
    top_k: int,
) -> RankingChangeMetrics:
    """
    Compute ranking change metrics comparing pre- and post-reranking orderings.

    Args:
        candidates: Ordered candidate list before reranking.
        reranked:   Ordered result list after reranking.
        top_k:      Threshold for computing top-K overlap.

    Returns:
        RankingChangeMetrics with displacement, overlap, and Spearman statistics.
    """
    n = len(reranked)
    if n == 0:
        return RankingChangeMetrics(
            mean_rank_displacement=0.0,
            top_1_changed=False,
            top_k_overlap_ratio=0.0,
            spearman_correlation=None,
            promoted_count=0,
            demoted_count=0,
            unchanged_count=0,
        )

    # Mean absolute rank displacement
    total_displacement = sum(abs(r.rank_delta) for r in reranked)
    mean_displacement = total_displacement / n

    # Promoted / demoted / unchanged
    promoted = sum(1 for r in reranked if r.rank_delta > 0)
    demoted = sum(1 for r in reranked if r.rank_delta < 0)
    unchanged = sum(1 for r in reranked if r.rank_delta == 0)

    # Top-1 changed?
    initial_top_1 = candidates[0].chunk_id if candidates else None
    final_top_1 = reranked[0].chunk_id if reranked else None
    top_1_changed = initial_top_1 != final_top_1

    # Top-K Jaccard overlap
    k = min(top_k, len(candidates), n)
    pre_top_k = {c.chunk_id for c in candidates[:k]}
    post_top_k = {r.chunk_id for r in reranked[:k]}
    union = pre_top_k | post_top_k
    intersection = pre_top_k & post_top_k
    jaccard = len(intersection) / len(union) if union else 0.0

    # Spearman correlation
    # Only consider chunk_ids present in both sets
    pre_rank_map = {c.chunk_id: (idx + 1) for idx, c in enumerate(candidates)}
    reranked_chunk_ids_in_order = [r.chunk_id for r in reranked]
    paired_pre: list[int] = []
    paired_post: list[int] = []
    for post_rank, cid in enumerate(reranked_chunk_ids_in_order, start=1):
        if cid in pre_rank_map:
            paired_pre.append(pre_rank_map[cid])
            paired_post.append(post_rank)

    spearman = _spearman_correlation(paired_pre, paired_post)

    return RankingChangeMetrics(
        mean_rank_displacement=round(mean_displacement, 4),
        top_1_changed=top_1_changed,
        top_k_overlap_ratio=round(jaccard, 4),
        spearman_correlation=round(spearman, 4) if spearman is not None else None,
        promoted_count=promoted,
        demoted_count=demoted,
        unchanged_count=unchanged,
    )


def compute_latency(
    retrieval_ms: float,
    reranking_ms: float,
    total_ms: float,
) -> "LatencyMetrics":  # type: ignore[name-defined]  # imported lazily
    from app.reranking.models import LatencyMetrics
    return LatencyMetrics(
        retrieval_latency_ms=round(retrieval_ms, 4),
        reranking_latency_ms=round(reranking_ms, 4),
        total_latency_ms=round(total_ms, 4),
    )
