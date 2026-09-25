"""
Unit tests for retrieval metrics: Recall@K, MRR, and Context Relevance.
"""

from __future__ import annotations

import pytest

from evals.metrics.retrieval import (
    compute_context_relevance,
    compute_mrr,
    compute_recall_at_k,
)


def pytest_approx(val: float) -> float:
    return pytest.approx(val, rel=1e-4)


def test_recall_at_k_known_relevance_sets() -> None:
    # Relevant chunks: c1, c2, c3 (total 3)
    relevant = {"c1", "c2", "c3"}

    # Case A: c1 at pos 0, c4 at pos 1, c2 at pos 2, c5 at pos 3, c3 at pos 4
    retrieved = ["c1", "c4", "c2", "c5", "c3", "c6", "c7"]

    assert compute_recall_at_k(retrieved, relevant, k=1) == pytest_approx(1.0 / 3.0)
    assert compute_recall_at_k(retrieved, relevant, k=2) == pytest_approx(1.0 / 3.0)
    assert compute_recall_at_k(retrieved, relevant, k=3) == pytest_approx(2.0 / 3.0)
    assert compute_recall_at_k(retrieved, relevant, k=5) == pytest_approx(3.0 / 3.0)
    assert compute_recall_at_k(retrieved, relevant, k=10) == pytest_approx(1.0)


def test_recall_at_k_empty_and_edge_cases() -> None:
    relevant = {"c1"}
    retrieved = ["c2", "c3"]

    # 0 matches
    assert compute_recall_at_k(retrieved, relevant, k=2) == 0.0
    assert compute_recall_at_k([], relevant, k=5) == 0.0
    assert compute_recall_at_k(retrieved, relevant, k=0) == 0.0

    # Unanswerable query (no relevant chunks expected)
    assert compute_recall_at_k(["c1", "c2"], set(), k=5) == 1.0


def test_mrr_rank_1() -> None:
    retrieved = ["chunk_target", "chunk_other_1", "chunk_other_2"]
    relevant = {"chunk_target"}
    assert compute_mrr(retrieved, relevant) == 1.0


def test_mrr_rank_3() -> None:
    retrieved = ["chunk_other_1", "chunk_other_2", "chunk_target", "chunk_other_3"]
    relevant = {"chunk_target"}
    assert compute_mrr(retrieved, relevant) == pytest_approx(1.0 / 3.0)


def test_mrr_no_relevant_item() -> None:
    retrieved = ["chunk_other_1", "chunk_other_2", "chunk_other_3"]
    relevant = {"chunk_target"}
    assert compute_mrr(retrieved, relevant) == 0.0


def test_mrr_empty_relevant() -> None:
    assert compute_mrr(["c1"], set()) == 1.0


def test_context_relevance_known_sets() -> None:
    # 2 relevant out of top 5
    retrieved = ["c1", "c2", "c3", "c4", "c5"]
    relevant = {"c1", "c3"}
    assert compute_context_relevance(retrieved, relevant, k=5) == pytest_approx(2.0 / 5.0)

    # 0 relevant out of top 5
    assert compute_context_relevance(retrieved, {"c99"}, k=5) == 0.0

    # 5 relevant out of top 5
    assert compute_context_relevance(retrieved, set(retrieved), k=5) == 1.0


def test_retrieval_metrics_determinism() -> None:
    retrieved = ["doc1:1", "doc2:2", "doc3:3", "doc4:4"]
    relevant = {"doc2:2", "doc5:5"}

    recall_runs = [compute_recall_at_k(retrieved, relevant, k=3) for _ in range(20)]
    mrr_runs = [compute_mrr(retrieved, relevant) for _ in range(20)]
    ctx_runs = [compute_context_relevance(retrieved, relevant, k=3) for _ in range(20)]

    assert len(set(recall_runs)) == 1
    assert len(set(mrr_runs)) == 1
    assert len(set(ctx_runs)) == 1
