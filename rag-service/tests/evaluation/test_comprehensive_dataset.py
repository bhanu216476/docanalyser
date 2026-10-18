"""
Unit tests for the comprehensive evaluation benchmark dataset and category metrics.
"""

from __future__ import annotations

from pathlib import Path

from app.evaluation.dataset import EvaluationCase, load_evaluation_dataset
from app.evaluation.runner import EvaluationRunner
from tests.evaluation.test_runner import FakeEvaluationPipeline


def test_comprehensive_dataset_loads_and_has_all_categories() -> None:
    dataset_path = (
        Path(__file__).parents[2]
        / "app"
        / "evaluation"
        / "datasets"
        / "comprehensive_eval_dataset.json"
    )
    assert dataset_path.exists(), f"Benchmark dataset not found at {dataset_path}"

    cases = load_evaluation_dataset(dataset_path)
    assert len(cases) >= 50, f"Expected at least 50 benchmark cases, got {len(cases)}"

    # Check required categories
    categories = {case.category for case in cases if case.category}
    expected_categories = {
        "exact_fact",
        "semantic",
        "multi_chunk",
        "multi_document",
        "insufficient_evidence",
        "misleading_assumption",
        "page_citation",
    }
    assert expected_categories.issubset(categories), (
        f"Missing categories: {expected_categories - categories}"
    )

    # Verify each case has valid fields
    for case in cases:
        assert case.id and case.id.strip()
        assert case.question and case.question.strip()
        assert case.category in expected_categories


def test_evaluation_runner_aggregates_per_category_metrics() -> None:
    pipeline = FakeEvaluationPipeline()
    test_cases = [
        EvaluationCase(
            id="c1",
            question="Fact question",
            category="exact_fact",
            relevant_chunk_ids=["chunk-1"],
        ),
        EvaluationCase(
            id="c2",
            question="Semantic question",
            category="semantic",
            relevant_chunk_ids=["chunk-1"],
        ),
    ]

    runner = EvaluationRunner(dataset=test_cases, pipeline=pipeline)
    report = runner.run()

    assert report.total_cases == 2
    assert report.completed_cases == 2
    assert "exact_fact" in report.per_category_metrics
    assert "semantic" in report.per_category_metrics
    assert report.per_category_metrics["exact_fact"]["count"] == 1
    assert report.per_category_metrics["semantic"]["count"] == 1
