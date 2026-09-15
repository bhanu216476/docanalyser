"""
Reranking Experiment Framework.

Runs single or batch query experiments through the RerankedPipeline,
collecting per-query and aggregate metrics.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Optional

from app.retrieval.models import RetrievalFilter
from app.reranking.models import (
    RerankExperimentBatchReport,
    RerankExperimentResult,
)
from app.reranking.pipeline import RerankedPipeline

logger = logging.getLogger(__name__)


class RerankingExperimentFramework:
    """
    Orchestrates single or batch reranking experiments.

    Collects per-query results and produces aggregate batch reports.

    Args:
        pipeline: Configured RerankedPipeline instance.
    """

    def __init__(self, pipeline: RerankedPipeline) -> None:
        self.pipeline = pipeline

    def run_single(
        self,
        query: str,
        filters: Optional[RetrievalFilter] = None,
        top_k: Optional[int] = None,
        candidate_k: Optional[int] = None,
    ) -> RerankExperimentResult:
        """
        Run a single query through the pipeline and return a detailed result.
        """
        logger.info("Running single rerank experiment: query_len=%d", len(query))
        result = self.pipeline.run(
            query=query,
            filters=filters,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        logger.info(
            "Single experiment done: retrieval=%dms, reranking=%dms, total=%dms",
            result.latency.retrieval_latency_ms,
            result.latency.reranking_latency_ms,
            result.latency.total_latency_ms,
        )
        return result

    def run_batch(
        self,
        queries: Sequence[str],
        filters: Optional[RetrievalFilter] = None,
        top_k: Optional[int] = None,
        candidate_k: Optional[int] = None,
    ) -> RerankExperimentBatchReport:
        """
        Run multiple queries and aggregate results into a batch report.

        Args:
            queries:     List of query strings.
            filters:     Optional metadata filter applied to all queries.
            top_k:       Override final top-K for all queries.
            candidate_k: Override candidate pool size for all queries.

        Returns:
            RerankExperimentBatchReport with per-query results and summary statistics.
        """
        if not queries:
            return RerankExperimentBatchReport(
                total_queries=0,
                mean_retrieval_latency_ms=0.0,
                mean_reranking_latency_ms=0.0,
                mean_total_latency_ms=0.0,
                mean_rank_displacement=0.0,
                top_1_change_rate=0.0,
                mean_top_k_overlap_ratio=0.0,
                mean_spearman_correlation=None,
                query_results=[],
            )

        results: list[RerankExperimentResult] = []
        for i, query in enumerate(queries, start=1):
            logger.info("Batch experiment query %d/%d", i, len(queries))
            try:
                result = self.pipeline.run(
                    query=query,
                    filters=filters,
                    top_k=top_k,
                    candidate_k=candidate_k,
                )
                results.append(result)
            except Exception as exc:
                logger.error("Query %d failed during batch experiment: %s", i, exc)
                raise

        total = len(results)

        mean_retrieval = sum(r.latency.retrieval_latency_ms for r in results) / total
        mean_reranking = sum(r.latency.reranking_latency_ms for r in results) / total
        mean_total = sum(r.latency.total_latency_ms for r in results) / total
        mean_displacement = (
            sum(r.ranking_metrics.mean_rank_displacement for r in results) / total
        )
        top_1_change_rate = (
            sum(1 for r in results if r.ranking_metrics.top_1_changed) / total
        )
        mean_overlap = (
            sum(r.ranking_metrics.top_k_overlap_ratio for r in results) / total
        )

        spearman_values = [
            r.ranking_metrics.spearman_correlation
            for r in results
            if r.ranking_metrics.spearman_correlation is not None
        ]
        mean_spearman = (
            sum(spearman_values) / len(spearman_values) if spearman_values else None
        )

        return RerankExperimentBatchReport(
            total_queries=total,
            mean_retrieval_latency_ms=round(mean_retrieval, 4),
            mean_reranking_latency_ms=round(mean_reranking, 4),
            mean_total_latency_ms=round(mean_total, 4),
            mean_rank_displacement=round(mean_displacement, 4),
            top_1_change_rate=round(top_1_change_rate, 4),
            mean_top_k_overlap_ratio=round(mean_overlap, 4),
            mean_spearman_correlation=(
                round(mean_spearman, 4) if mean_spearman is not None else None
            ),
            query_results=results,
        )

    def format_single_report(self, result: RerankExperimentResult) -> str:
        """Render a human-readable summary of a single experiment result."""
        lines = [
            f"## Reranking Experiment Result",
            f"**Query**: {result.query!r}",
            f"**Candidates before reranking**: {result.candidate_count}",
            f"**Results after reranking**: {len(result.reranked_results)}",
            "",
            "### Latency",
            f"- Retrieval: {result.latency.retrieval_latency_ms:.2f} ms",
            f"- Reranking: {result.latency.reranking_latency_ms:.2f} ms",
            f"- Total:     {result.latency.total_latency_ms:.2f} ms",
            "",
            "### Ranking Change Metrics",
            f"- Mean Rank Displacement: {result.ranking_metrics.mean_rank_displacement:.4f}",
            f"- Top-1 Changed:          {result.ranking_metrics.top_1_changed}",
            f"- Top-K Overlap (Jaccard): {result.ranking_metrics.top_k_overlap_ratio:.4f}",
            f"- Spearman Correlation:   {result.ranking_metrics.spearman_correlation}",
            f"- Promoted:  {result.ranking_metrics.promoted_count}",
            f"- Demoted:   {result.ranking_metrics.demoted_count}",
            f"- Unchanged: {result.ranking_metrics.unchanged_count}",
            "",
            "### Reranked Results",
        ]
        for r in result.reranked_results:
            direction = (
                "▲" if r.rank_delta > 0 else ("▼" if r.rank_delta < 0 else "═")
            )
            lines.append(
                f"  [{r.reranked_rank}] {r.chunk_id} "
                f"(ret_score={r.retrieval_score:.4f}, rerank_score={r.reranker_score:.4f}, "
                f"{direction} {abs(r.rank_delta)})"
            )
        return "\n".join(lines)

    def format_batch_report(self, report: RerankExperimentBatchReport) -> str:
        """Render a human-readable summary of a batch experiment report."""
        lines = [
            f"## Batch Reranking Experiment Report",
            f"**Total Queries**: {report.total_queries}",
            "",
            "### Average Latency",
            f"- Retrieval: {report.mean_retrieval_latency_ms:.2f} ms",
            f"- Reranking: {report.mean_reranking_latency_ms:.2f} ms",
            f"- Total:     {report.mean_total_latency_ms:.2f} ms",
            "",
            "### Aggregate Ranking Metrics",
            f"- Mean Rank Displacement: {report.mean_rank_displacement:.4f}",
            f"- Top-1 Change Rate:      {report.top_1_change_rate:.2%}",
            f"- Mean Top-K Overlap:     {report.mean_top_k_overlap_ratio:.4f}",
            f"- Mean Spearman Corr:     {report.mean_spearman_correlation}",
        ]
        return "\n".join(lines)
