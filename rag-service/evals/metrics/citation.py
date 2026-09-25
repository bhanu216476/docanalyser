"""
Citation metrics: Precision, Recall, and Accuracy against expected evidence.
"""

from __future__ import annotations

from collections.abc import Sequence, Set
from typing import Union


def evaluate_citation_metrics(
    generated_chunk_ids: Sequence[str],
    expected_chunk_ids: Union[Set[str], Sequence[str]],
) -> tuple[float, float, float]:
    """
    Evaluate generated citations against ground-truth expected chunks.

    Args:
        generated_chunk_ids: Chunk IDs corresponding to verified generated citations.
        expected_chunk_ids: Expected ground-truth chunk IDs.

    Returns:
        tuple of (precision, recall, accuracy)
        - precision = correct_citations / generated_citations (1.0 if both 0)
        - recall = correct_citations / expected_citations (1.0 if both 0)
        - accuracy = Jaccard index: intersection / union (1.0 if both 0)
    """
    gen_set = set(generated_chunk_ids)
    exp_set = set(expected_chunk_ids)

    if not gen_set and not exp_set:
        return (1.0, 1.0, 1.0)

    if not gen_set:
        return (0.0, 0.0, 0.0)

    if not exp_set:
        # Generated citations when none expected (over-citation or hallucination)
        return (0.0, 1.0, 0.0)

    matched = gen_set & exp_set
    union = gen_set | exp_set

    precision = len(matched) / float(len(gen_set))
    recall = len(matched) / float(len(exp_set))
    accuracy = len(matched) / float(len(union))

    return (round(precision, 4), round(recall, 4), round(accuracy, 4))
