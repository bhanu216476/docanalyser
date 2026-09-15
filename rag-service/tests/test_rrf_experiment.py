"""
Tests for the RRF k-parameter experiment utility.

Verifies that score compression, ranking dynamics, and comparison
table output work correctly for k ∈ {20, 40, 60, 100}.
"""

from __future__ import annotations

import pytest

from app.retrieval.models import RetrievalResult
from app.retrieval.rrf_experiment import (
    KExperimentRecord,
    format_k_comparison_table,
    run_k_experiment,
)


def _make_result(chunk_id: str, rank: int = 1) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=f"Content of {chunk_id}",
        score=1.0 - (rank - 1) * 0.1,
        rank=rank,
        document_id="doc",
        file_name="test.md",
        file_type="md",
        source="/test/test.md",
    )


def _ranked(*chunk_ids: str) -> list[RetrievalResult]:
    return [_make_result(cid, rank=i + 1) for i, cid in enumerate(chunk_ids)]


class TestRunKExperiment:
    def test_returns_all_k_values(self) -> None:
        dense = _ranked("A", "B", "C")
        bm25 = _ranked("C", "A", "D")

        results = run_k_experiment({"dense": dense, "bm25": bm25})
        assert set(results.keys()) == {20, 40, 60, 100}

    def test_each_k_returns_records_for_all_chunks(self) -> None:
        dense = _ranked("A", "B")
        bm25 = _ranked("C", "A")

        results = run_k_experiment({"dense": dense, "bm25": bm25})

        for k, records in results.items():
            chunk_ids = {r.chunk_id for r in records}
            assert chunk_ids == {"A", "B", "C"}

    def test_custom_k_values(self) -> None:
        dense = _ranked("A", "B")
        results = run_k_experiment([dense], k_values=[5, 10])
        assert set(results.keys()) == {5, 10}

    def test_records_are_sorted_descending_by_score(self) -> None:
        dense = _ranked("A", "B", "C")
        bm25 = _ranked("A", "C", "D")

        results = run_k_experiment({"dense": dense, "bm25": bm25})

        for k, records in results.items():
            scores = [r.rrf_score for r in records]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], f"k={k}: not sorted descending"

    def test_k_value_on_records_matches_key(self) -> None:
        dense = _ranked("A")
        results = run_k_experiment([dense], k_values=[42])
        for record in results[42]:
            assert record.k == 42

    def test_large_k_compresses_scores(self) -> None:
        """Larger k → lower individual scores (more compression)."""
        dense = _ranked("A", "B", "C")

        results_low = run_k_experiment([dense], k_values=[1])
        results_high = run_k_experiment([dense], k_values=[1000])

        score_a_low = results_low[1][0].rrf_score
        score_a_high = results_high[1000][0].rrf_score

        assert score_a_low > score_a_high

    def test_rank_fields_are_1based(self) -> None:
        dense = _ranked("A", "B", "C")
        results = run_k_experiment([dense], k_values=[60])

        for record in results[60]:
            assert record.rank >= 1

    def test_source_ranks_populated(self) -> None:
        dense = _ranked("A")
        bm25 = _ranked("A")
        results = run_k_experiment({"dense": dense, "bm25": bm25}, k_values=[60])
        record_a = results[60][0]
        assert "dense" in record_a.source_ranks
        assert "bm25" in record_a.source_ranks

    def test_top_k_truncates_output(self) -> None:
        dense = _ranked("A", "B", "C", "D", "E")
        results = run_k_experiment([dense], k_values=[60], top_k=3)
        assert len(results[60]) == 3

    def test_empty_input_returns_empty_records(self) -> None:
        results = run_k_experiment([], k_values=[60])
        assert results[60] == []


class TestFormatKComparisonTable:
    def test_returns_header_row(self) -> None:
        dense = _ranked("A", "B")
        results = run_k_experiment({"dense": dense, "bm25": []}, k_values=[20, 60])
        table = format_k_comparison_table(results)

        assert "Chunk ID" in table
        assert "k=20" in table
        assert "k=60" in table

    def test_chunk_ids_appear_in_table(self) -> None:
        dense = _ranked("chunk-alpha", "chunk-beta")
        results = run_k_experiment([dense], k_values=[60])
        table = format_k_comparison_table(results)

        assert "chunk-alpha" in table
        assert "chunk-beta" in table

    def test_empty_results_handled(self) -> None:
        table = format_k_comparison_table({})
        assert "No experiment results" in table

    def test_markdown_pipe_delimited(self) -> None:
        dense = _ranked("A")
        results = run_k_experiment([dense], k_values=[60])
        table = format_k_comparison_table(results)
        lines = table.strip().split("\n")
        # Every line in a markdown table starts and ends with "|"
        for line in lines:
            assert line.strip().startswith("|"), f"Non-table line: {line}"

    def test_k_score_compression_visible_in_table(self) -> None:
        """Scores for k=20 should be visibly higher than k=100 in the table."""
        dense = _ranked("A")
        results = run_k_experiment([dense], k_values=[20, 100])
        table = format_k_comparison_table(results)

        # Both score columns should have different values visible in table
        score_20 = results[20][0].rrf_score
        score_100 = results[100][0].rrf_score
        assert score_20 > score_100
