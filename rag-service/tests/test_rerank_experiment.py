"""
Tests for the RerankedPipeline and RerankingExperimentFramework.

Uses MockReranker and deterministic mock retrievers for fully offline tests.
"""

from __future__ import annotations

from typing import Optional

import pytest

from app.retrieval.models import RetrievalFilter, RetrievalResult
from app.reranking.experiment import RerankingExperimentFramework
from app.reranking.mock_reranker import MockReranker
from app.reranking.models import (
    LatencyMetrics,
    RankingChangeMetrics,
    RerankExperimentBatchReport,
    RerankExperimentResult,
)
from app.reranking.pipeline import RerankedPipeline


# ---------------------------------------------------------------------------
# Mock Retriever
# ---------------------------------------------------------------------------

class MockRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        return self._results[:top_k]


def _make_result(chunk_id: str, score: float, rank: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=f"Document {chunk_id} about authentication policy and security",
        score=score,
        rank=rank,
        document_id="doc",
        file_name="test.md",
        file_type="md",
        source="/test.md",
    )


def _four_candidates() -> list[RetrievalResult]:
    return [
        _make_result("A", 0.95, 1),
        _make_result("B", 0.80, 2),
        _make_result("C", 0.65, 3),
        _make_result("D", 0.50, 4),
    ]


def _make_pipeline(custom_scores: dict | None = None, top_k: int = 3) -> RerankedPipeline:
    retriever = MockRetriever(_four_candidates())
    reranker = MockReranker(custom_scores=custom_scores or {})
    return RerankedPipeline(retriever=retriever, reranker=reranker, top_k=top_k, candidate_k=10)


# ---------------------------------------------------------------------------
# RerankedPipeline — basic behaviour
# ---------------------------------------------------------------------------

class TestRerankedPipeline:
    def test_returns_experiment_result(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("authentication policy")
        assert isinstance(result, RerankExperimentResult)

    def test_result_has_correct_query(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("my search query")
        assert result.query == "my search query"

    def test_reranked_results_top_k_respected(self) -> None:
        pipeline = _make_pipeline(top_k=2)
        result = pipeline.run("query")
        assert len(result.reranked_results) == 2

    def test_initial_results_preserved(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert len(result.initial_results) > 0

    def test_candidate_count_matches_retrieval(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert result.candidate_count == len(result.initial_results)

    def test_retrieval_score_preserved(self) -> None:
        """retrieval_score must match original candidate scores."""
        pipeline = _make_pipeline(custom_scores={"A": 0.99, "B": 0.01, "C": 0.50, "D": 0.25})
        result = pipeline.run("query")

        score_map = {c.chunk_id: c.score for c in result.initial_results}
        for rr in result.reranked_results:
            original = score_map[rr.chunk_id]
            assert rr.retrieval_score == pytest.approx(original)

    def test_reranker_and_retrieval_scores_differ(self) -> None:
        """After reranking, the reranker score should not simply mirror the retrieval score."""
        pipeline = _make_pipeline(custom_scores={"A": 0.1, "B": 0.9, "C": 0.5, "D": 0.3})
        result = pipeline.run("query")
        retrieval_order = [r.chunk_id for r in result.initial_results]
        reranked_order = [r.chunk_id for r in result.reranked_results]
        # With these scores B should end up rank 1 despite being initial rank 2
        assert reranked_order[0] == "B"


# ---------------------------------------------------------------------------
# Latency measurements
# ---------------------------------------------------------------------------

class TestLatencyMeasurements:
    def test_latency_fields_are_non_negative(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert result.latency.retrieval_latency_ms >= 0.0
        assert result.latency.reranking_latency_ms >= 0.0
        assert result.latency.total_latency_ms >= 0.0

    def test_total_latency_ge_sum_of_parts(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        partial_sum = (
            result.latency.retrieval_latency_ms + result.latency.reranking_latency_ms
        )
        assert result.latency.total_latency_ms >= partial_sum - 0.1  # small tolerance

    def test_latency_is_finite(self) -> None:
        import math
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert math.isfinite(result.latency.retrieval_latency_ms)
        assert math.isfinite(result.latency.reranking_latency_ms)
        assert math.isfinite(result.latency.total_latency_ms)


# ---------------------------------------------------------------------------
# Ranking metrics
# ---------------------------------------------------------------------------

class TestRankingMetrics:
    def test_metrics_has_expected_fields(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        m = result.ranking_metrics
        assert hasattr(m, "mean_rank_displacement")
        assert hasattr(m, "top_1_changed")
        assert hasattr(m, "top_k_overlap_ratio")
        assert hasattr(m, "spearman_correlation")
        assert hasattr(m, "promoted_count")
        assert hasattr(m, "demoted_count")
        assert hasattr(m, "unchanged_count")

    def test_displacement_non_negative(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert result.ranking_metrics.mean_rank_displacement >= 0.0

    def test_top_k_overlap_is_between_0_and_1(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        assert 0.0 <= result.ranking_metrics.top_k_overlap_ratio <= 1.0

    def test_promoted_demoted_unchanged_sum_to_reranked_count(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        m = result.ranking_metrics
        total = m.promoted_count + m.demoted_count + m.unchanged_count
        assert total == len(result.reranked_results)

    def test_no_reranking_change_gives_perfect_overlap(self) -> None:
        """When reranker score perfectly preserves original order, top-k overlap should be 1."""
        # Assign scores in original ranking order to preserve order
        pipeline = _make_pipeline(custom_scores={"A": 0.9, "B": 0.7, "C": 0.5, "D": 0.3}, top_k=4)
        result = pipeline.run("query")
        assert result.ranking_metrics.top_k_overlap_ratio == pytest.approx(1.0)

    def test_top_1_changed_when_rank1_changes(self) -> None:
        """With scores forcing D to rank 1, top_1 must be marked as changed."""
        pipeline = _make_pipeline(custom_scores={"A": 0.1, "B": 0.2, "C": 0.3, "D": 0.99})
        result = pipeline.run("query")
        # D was rank 4 initially, now rank 1 → top_1_changed=True
        assert result.ranking_metrics.top_1_changed is True

    def test_spearman_present_for_multiple_candidates(self) -> None:
        pipeline = _make_pipeline()
        result = pipeline.run("query")
        # With 4 candidates, Spearman should be computable
        assert result.ranking_metrics.spearman_correlation is not None


# ---------------------------------------------------------------------------
# Empty pipeline
# ---------------------------------------------------------------------------

class TestEmptyPipeline:
    def test_empty_retriever_returns_zero_candidates(self) -> None:
        retriever = MockRetriever([])
        reranker = MockReranker()
        pipeline = RerankedPipeline(retriever=retriever, reranker=reranker, top_k=3, candidate_k=10)
        result = pipeline.run("query")
        assert result.candidate_count == 0
        assert result.reranked_results == []

    def test_pipeline_constructor_validates_top_k(self) -> None:
        retriever = MockRetriever([])
        reranker = MockReranker()
        with pytest.raises(ValueError):
            RerankedPipeline(retriever=retriever, reranker=reranker, top_k=0)


# ---------------------------------------------------------------------------
# RerankingExperimentFramework
# ---------------------------------------------------------------------------

class TestRerankingExperimentFramework:
    def test_run_single_returns_result(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        result = framework.run_single("authentication security")
        assert isinstance(result, RerankExperimentResult)

    def test_run_batch_returns_report(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        report = framework.run_batch(["authentication", "security policy"])
        assert isinstance(report, RerankExperimentBatchReport)
        assert report.total_queries == 2

    def test_batch_empty_queries(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        report = framework.run_batch([])
        assert report.total_queries == 0

    def test_batch_aggregates_latencies(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        report = framework.run_batch(["q1", "q2", "q3"])
        assert report.mean_total_latency_ms >= 0.0

    def test_batch_top_1_change_rate_bounded(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        report = framework.run_batch(["q1", "q2"])
        assert 0.0 <= report.top_1_change_rate <= 1.0

    def test_format_single_report_string(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        result = framework.run_single("query")
        report_str = framework.format_single_report(result)
        assert isinstance(report_str, str)
        assert "Reranking" in report_str
        assert "Latency" in report_str

    def test_format_batch_report_string(self) -> None:
        pipeline = _make_pipeline()
        framework = RerankingExperimentFramework(pipeline)
        report = framework.run_batch(["query"])
        report_str = framework.format_batch_report(report)
        assert isinstance(report_str, str)
        assert "Total Queries" in report_str
