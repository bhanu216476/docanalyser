"""
Unit tests for Reciprocal Rank Fusion (RRF) algorithm.

Includes hand-calculated expected values and exhaustive edge-case coverage.
"""

from __future__ import annotations

import pytest

from app.retrieval.models import HybridRetrievalResult, RetrievalResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(chunk_id: str, score: float = 1.0, rank: int = 1) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=f"Content of {chunk_id}",
        score=score,
        rank=rank,
        metadata={"test": True},
        document_id="doc-1",
        file_name="test.md",
        file_type="md",
        source="/test/test.md",
    )


def _ranked(*chunk_ids: str) -> list[RetrievalResult]:
    """Create a ranked list of RetrievalResult with 1-based ranks."""
    return [_make_result(cid, score=1.0 - i * 0.1, rank=i + 1) for i, cid in enumerate(chunk_ids)]


# ---------------------------------------------------------------------------
# Importing the function under test
# ---------------------------------------------------------------------------

from app.retrieval.rrf import reciprocal_rank_fusion


# ---------------------------------------------------------------------------
# Hand-calculated expected values
# ---------------------------------------------------------------------------

class TestRRFHandCalculated:
    """
    Manually verified RRF calculations.

    Formula: RRF(d) = Σ 1 / (k + r_i(d))

    Example:
        Dense:  A → rank 1, B → rank 2, C → rank 3
        BM25:   C → rank 1, A → rank 2, D → rank 3

        k = 60:
            A = 1/(60+1) + 1/(60+2) = 1/61 + 1/62 ≈ 0.0163934 + 0.0161290 = 0.0325224
            B = 1/(60+2)             = 1/62           ≈ 0.0161290
            C = 1/(60+3) + 1/(60+1) = 1/63 + 1/61   ≈ 0.0158730 + 0.0163934 = 0.0322664
            D = 1/(60+3)             = 1/63           ≈ 0.0158730

        Expected order (desc): A, C, B, D
    """

    def test_hand_calculated_k60(self) -> None:
        dense = _ranked("A", "B", "C")
        bm25 = _ranked("C", "A", "D")
        k = 60

        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=k)

        assert len(results) == 4
        chunk_ids = [r.chunk_id for r in results]
        assert chunk_ids == ["A", "C", "B", "D"]

        expected_a = 1 / (60 + 1) + 1 / (60 + 2)
        expected_c = 1 / (60 + 3) + 1 / (60 + 1)
        expected_b = 1 / (60 + 2)
        expected_d = 1 / (60 + 3)

        assert results[0].rrf_score == pytest.approx(expected_a, rel=1e-6)
        assert results[1].rrf_score == pytest.approx(expected_c, rel=1e-6)
        assert results[2].rrf_score == pytest.approx(expected_b, rel=1e-6)
        assert results[3].rrf_score == pytest.approx(expected_d, rel=1e-6)

    def test_hand_calculated_k20(self) -> None:
        dense = _ranked("A", "B", "C")
        bm25 = _ranked("C", "A", "D")
        k = 20

        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=k)
        chunk_ids = [r.chunk_id for r in results]

        expected_a = 1 / (20 + 1) + 1 / (20 + 2)
        expected_c = 1 / (20 + 3) + 1 / (20 + 1)
        expected_b = 1 / (20 + 2)
        expected_d = 1 / (20 + 3)

        # A and C should still be top-2 with k=20
        assert chunk_ids[0] == "A"
        assert chunk_ids[1] == "C"
        assert results[0].rrf_score == pytest.approx(expected_a, rel=1e-6)
        assert results[1].rrf_score == pytest.approx(expected_c, rel=1e-6)
        assert results[2].rrf_score == pytest.approx(expected_b, rel=1e-6)
        assert results[3].rrf_score == pytest.approx(expected_d, rel=1e-6)

    def test_rrf_scores_decrease_with_rank(self) -> None:
        """Higher-ranked docs should always have larger scores."""
        dense = _ranked("A", "B", "C", "D")
        results = reciprocal_rank_fusion([dense], k=60)
        scores = [r.rrf_score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


# ---------------------------------------------------------------------------
# Source rank metadata
# ---------------------------------------------------------------------------

class TestSourceRanks:
    def test_dense_rank_recorded(self) -> None:
        dense = _ranked("A", "B")
        bm25: list[RetrievalResult] = []
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)
        a = next(r for r in results if r.chunk_id == "A")
        assert a.dense_rank == 1
        assert a.bm25_rank is None

    def test_bm25_rank_recorded(self) -> None:
        dense: list[RetrievalResult] = []
        bm25 = _ranked("X", "Y")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)
        x = next(r for r in results if r.chunk_id == "X")
        assert x.dense_rank is None
        assert x.bm25_rank == 1

    def test_both_ranks_recorded(self) -> None:
        dense = _ranked("A", "B")
        bm25 = _ranked("B", "A")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)

        a = next(r for r in results if r.chunk_id == "A")
        b = next(r for r in results if r.chunk_id == "B")

        assert a.dense_rank == 1
        assert a.bm25_rank == 2
        assert b.dense_rank == 2
        assert b.bm25_rank == 1

    def test_source_ranks_dict(self) -> None:
        dense = _ranked("A")
        bm25 = _ranked("A")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)
        assert results[0].source_ranks["dense"] == 1
        assert results[0].source_ranks["bm25"] == 1


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_both_empty(self) -> None:
        results = reciprocal_rank_fusion({"dense": [], "bm25": []}, k=60)
        assert results == []

    def test_empty_dense_only_bm25(self) -> None:
        bm25 = _ranked("X", "Y")
        results = reciprocal_rank_fusion({"dense": [], "bm25": bm25}, k=60)
        assert len(results) == 2
        assert results[0].chunk_id == "X"

    def test_empty_bm25_only_dense(self) -> None:
        dense = _ranked("A", "B")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": []}, k=60)
        assert len(results) == 2
        assert results[0].chunk_id == "A"

    def test_sequence_input_empty(self) -> None:
        results = reciprocal_rank_fusion([], k=60)
        assert results == []


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

class TestDuplicateHandling:
    def test_dedup_within_single_list(self) -> None:
        """Duplicate chunk_id in the same list: only first occurrence (best rank) counts."""
        dup_list = [
            _make_result("A", score=0.9, rank=1),
            _make_result("A", score=0.8, rank=2),
        ]
        results = reciprocal_rank_fusion([dup_list], k=60)
        # A should appear once
        ids = [r.chunk_id for r in results]
        assert ids.count("A") == 1
        # Score should come from rank=1 only
        expected_a = 1 / (60 + 1)
        assert results[0].rrf_score == pytest.approx(expected_a, rel=1e-6)

    def test_doc_in_both_gets_both_contributions(self) -> None:
        """A chunk in both Dense and BM25 must receive contributions from both."""
        dense = _ranked("A")
        bm25 = _ranked("A")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)

        assert len(results) == 1
        expected = 1 / (60 + 1) + 1 / (60 + 1)
        assert results[0].rrf_score == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# Deterministic tie-breaking
# ---------------------------------------------------------------------------

class TestDeterministicTieBreaking:
    def test_tie_breaks_on_chunk_id_alphabetically(self) -> None:
        """When two docs have equal scores, chunk_id alphabetical order is used."""
        # "A" and "B" each appear in only one list at rank 1 with k=60
        # Both get score = 1/(60+1) ≈ 0.01639
        dense = [_make_result("B", rank=1)]
        bm25 = [_make_result("A", rank=1)]
        results = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)

        assert results[0].rrf_score == pytest.approx(results[1].rrf_score, rel=1e-6)
        # Alphabetically "A" < "B"
        assert results[0].chunk_id == "A"
        assert results[1].chunk_id == "B"

    def test_repeated_runs_produce_same_order(self) -> None:
        dense = _ranked("Z", "M", "A")
        bm25 = _ranked("A", "Z", "Q")

        results1 = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)
        results2 = reciprocal_rank_fusion({"dense": dense, "bm25": bm25}, k=60)

        ids1 = [r.chunk_id for r in results1]
        ids2 = [r.chunk_id for r in results2]
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# top_k truncation
# ---------------------------------------------------------------------------

class TestTopKTruncation:
    def test_top_k_limits_output(self) -> None:
        dense = _ranked("A", "B", "C", "D")
        results = reciprocal_rank_fusion([dense], k=60, top_k=2)
        assert len(results) == 2

    def test_top_k_none_returns_all(self) -> None:
        dense = _ranked("A", "B", "C", "D")
        results = reciprocal_rank_fusion([dense], k=60, top_k=None)
        assert len(results) == 4

    def test_top_k_larger_than_candidates(self) -> None:
        dense = _ranked("A", "B")
        results = reciprocal_rank_fusion([dense], k=60, top_k=100)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# k validation
# ---------------------------------------------------------------------------

class TestKValidation:
    def test_k_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            reciprocal_rank_fusion([_ranked("A")], k=0)

    def test_k_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            reciprocal_rank_fusion([_ranked("A")], k=-10)

    def test_top_k_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            reciprocal_rank_fusion([_ranked("A")], k=60, top_k=0)


# ---------------------------------------------------------------------------
# Multi-source (>2 ranking lists)
# ---------------------------------------------------------------------------

class TestMultiSource:
    def test_three_sources(self) -> None:
        s1 = _ranked("A", "B")
        s2 = _ranked("B", "C")
        s3 = _ranked("A", "C")

        results = reciprocal_rank_fusion([s1, s2, s3], k=60)
        chunk_ids = [r.chunk_id for r in results]

        # A appears in s1 (rank1) and s3 (rank1)
        # B appears in s1 (rank2) and s2 (rank1)
        # C appears in s2 (rank2) and s3 (rank2)
        expected_a = 1 / (61) + 1 / (61)
        expected_b = 1 / (62) + 1 / (61)
        expected_c = 1 / (62) + 1 / (62)

        a_res = next(r for r in results if r.chunk_id == "A")
        b_res = next(r for r in results if r.chunk_id == "B")
        c_res = next(r for r in results if r.chunk_id == "C")

        assert a_res.rrf_score == pytest.approx(expected_a, rel=1e-6)
        assert b_res.rrf_score == pytest.approx(expected_b, rel=1e-6)
        assert c_res.rrf_score == pytest.approx(expected_c, rel=1e-6)
        # A = 1/61 + 1/61 = 0.03279 > B = 1/62 + 1/61 = 0.03252 > C = 1/62 + 1/62 = 0.03226
        assert chunk_ids[0] == "A"


# ---------------------------------------------------------------------------
# Score vs. rank invariants
# ---------------------------------------------------------------------------

class TestScoreInvariants:
    def test_score_field_mirrors_rrf_score(self) -> None:
        dense = _ranked("A", "B")
        results = reciprocal_rank_fusion({"dense": dense, "bm25": []}, k=60)
        for r in results:
            assert r.score == pytest.approx(r.rrf_score, rel=1e-9)

    def test_rank_field_is_1based_and_sequential(self) -> None:
        dense = _ranked("A", "B", "C")
        results = reciprocal_rank_fusion([dense], k=60)
        for i, r in enumerate(results, start=1):
            assert r.rank == i

    def test_sequence_and_mapping_give_same_result(self) -> None:
        """Sequence input with auto-named sources ≈ mapping."""
        dense = _ranked("A", "B", "C")
        bm25 = _ranked("C", "A")

        # Use mapping form
        mapping_result = reciprocal_rank_fusion({"source_0": dense, "source_1": bm25}, k=60)
        # Use sequence form
        sequence_result = reciprocal_rank_fusion([dense, bm25], k=60)

        map_ids = [r.chunk_id for r in mapping_result]
        seq_ids = [r.chunk_id for r in sequence_result]
        assert map_ids == seq_ids

        for mr, sr in zip(mapping_result, sequence_result):
            assert mr.rrf_score == pytest.approx(sr.rrf_score, rel=1e-9)
