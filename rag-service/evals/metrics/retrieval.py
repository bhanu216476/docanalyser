"""
Retrieval metrics: Recall@K, MRR, and Context Relevance.
"""

from __future__ import annotations

from collections.abc import Sequence, Set
from typing import Union


def compute_recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Union[Set[str], Sequence[str]],
    k: int,
) -> float:
    """
    Compute Recall@K.

    Definition:
        Recall@K = (relevant ground-truth chunks retrieved in top K) / (total relevant ground-truth chunks)

    Args:
        retrieved_chunk_ids: Ordered sequence of retrieved chunk IDs.
        relevant_chunk_ids: Ground-truth relevant chunk IDs.
        k: Cut-off rank (1, 3, 5, 10, etc.).

    Returns:
        Float value in [0.0, 1.0]. Returns 1.0 if relevant_chunk_ids is empty
        (e.g. unanswerable query with no relevant evidence).
    """
    rel_set = set(relevant_chunk_ids)
    if not rel_set:
        return 1.0

    if k <= 0:
        return 0.0

    top_k_retrieved = set(retrieved_chunk_ids[:k])
    matched = len(top_k_retrieved & rel_set)
    return matched / float(len(rel_set))


def compute_mrr(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Union[Set[str], Sequence[str]],
) -> float:
    """
    Compute Reciprocal Rank (RR) for a single query.

    Definition:
        RR = 1 / rank_of_first_relevant_result (1-based rank)
        RR = 0 if no relevant result is retrieved.

    Args:
        retrieved_chunk_ids: Deterministically ordered list of retrieved chunk IDs.
        relevant_chunk_ids: Set/sequence of relevant chunk IDs.

    Returns:
        Reciprocal rank float in [0.0, 1.0].
    """
    rel_set = set(relevant_chunk_ids)
    if not rel_set:
        return 1.0

    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in rel_set:
            return 1.0 / float(rank)

    return 0.0


def compute_context_relevance(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Union[Set[str], Sequence[str]],
    k: int = 5,
) -> float:
    """
    Compute Context Relevance@K.

    Definition:
        Context Relevance@K = (number of relevant chunks in top K) / K

    Args:
        retrieved_chunk_ids: Sequence of retrieved chunk IDs.
        relevant_chunk_ids: Ground-truth relevant chunk IDs.
        k: Window size (default 5).

    Returns:
        Float in [0.0, 1.0].
    """
    if k <= 0:
        return 0.0

    rel_set = set(relevant_chunk_ids)
    if not rel_set:
        # If no relevant chunks exist in ground truth (e.g. unanswerable),
        # if retriever retrieved chunks, precision is 0; if 0 retrieved, precision is 1.0
        return 1.0 if len(retrieved_chunk_ids) == 0 else 0.0

    top_k_retrieved = retrieved_chunk_ids[:k]
    if not top_k_retrieved:
        return 0.0

    matched = sum(1 for cid in top_k_retrieved if cid in rel_set)
    return matched / float(k)
