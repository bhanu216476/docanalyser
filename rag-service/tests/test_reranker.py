"""
Unit tests for BaseReranker, MockReranker, and ranking metrics.
"""

from __future__ import annotations

import pytest

from app.retrieval.models import RetrievalResult
from app.reranking.base import BaseReranker, Reranker
from app.reranking.mock_reranker import MockReranker
from app.reranking.models import RerankedResult


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_result(
    chunk_id: str,
    score: float,
    rank: int,
    content: str | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=content or f"This is content for {chunk_id}",
        score=score,
        rank=rank,
        document_id="doc-1",
        file_name="test.md",
        file_type="md",
        source="/test.md",
    )


def _candidates() -> list[RetrievalResult]:
    return [
        _make_result("A", 0.8, 1, "authentication policy requirements"),
        _make_result("B", 0.7, 2, "database backup procedures"),
        _make_result("C", 0.6, 3, "authentication token lifetime"),
        _make_result("D", 0.5, 4, "network security firewall rules"),
    ]


# ---------------------------------------------------------------------------
# MockReranker — deterministic scoring
# ---------------------------------------------------------------------------

class TestMockRerankerDeterminism:
    def test_same_inputs_produce_same_scores(self) -> None:
        reranker = MockReranker()
        query = "authentication"
        cands = _candidates()

        result1 = reranker.rerank(query, cands)
        result2 = reranker.rerank(query, cands)

        assert [r.reranker_score for r in result1] == [r.reranker_score for r in result2]
        assert [r.chunk_id for r in result1] == [r.chunk_id for r in result2]

    def test_custom_scores_override_algorithm(self) -> None:
        custom = {"A": 0.95, "B": 0.10, "C": 0.80}
        reranker = MockReranker(custom_scores=custom)

        results = reranker.rerank("query", _candidates())

        score_map = {r.chunk_id: r.reranker_score for r in results}
        assert score_map["A"] == pytest.approx(0.95)
        assert score_map["B"] == pytest.approx(0.10)
        assert score_map["C"] == pytest.approx(0.80)

    def test_ranking_ordered_by_reranker_score_desc(self) -> None:
        reranker = MockReranker(custom_scores={"A": 0.3, "B": 0.9, "C": 0.6, "D": 0.1})
        results = reranker.rerank("query", _candidates())

        scores = [r.reranker_score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_reranked_rank_is_1based_sequential(self) -> None:
        reranker = MockReranker()
        results = reranker.rerank("test", _candidates())
        for i, r in enumerate(results, start=1):
            assert r.reranked_rank == i


# ---------------------------------------------------------------------------
# Score preservation
# ---------------------------------------------------------------------------

class TestScorePreservation:
    def test_retrieval_score_preserved_not_overwritten(self) -> None:
        """retrieval_score must match the original candidate score."""
        reranker = MockReranker(custom_scores={"A": 0.99})
        cand_a = _make_result("A", score=0.555, rank=1)
        results = reranker.rerank("query", [cand_a])

        assert results[0].retrieval_score == pytest.approx(0.555)
        assert results[0].reranker_score == pytest.approx(0.99)

    def test_retrieval_and_reranker_scores_can_differ(self) -> None:
        reranker = MockReranker(custom_scores={"A": 0.1, "B": 0.9})
        cands = [
            _make_result("A", score=0.95, rank=1),
            _make_result("B", score=0.50, rank=2),
        ]
        results = reranker.rerank("query", cands)

        result_b = next(r for r in results if r.chunk_id == "B")
        result_a = next(r for r in results if r.chunk_id == "A")

        # B reranked higher but originally ranked lower
        assert result_b.reranked_rank < result_a.reranked_rank
        assert result_b.retrieval_score == pytest.approx(0.50)
        assert result_b.reranker_score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Rank delta
# ---------------------------------------------------------------------------

class TestRankDelta:
    def test_promoted_has_positive_delta(self) -> None:
        """A doc that goes from rank 4 to rank 1 has delta = 4-1=3 > 0."""
        reranker = MockReranker(
            custom_scores={"A": 0.1, "B": 0.2, "C": 0.3, "D": 0.9}
        )
        results = reranker.rerank("query", _candidates())
        d_result = next(r for r in results if r.chunk_id == "D")
        # D was rank 4 initially, should be rank 1 now
        assert d_result.reranked_rank == 1
        assert d_result.retrieval_rank == 4
        assert d_result.rank_delta == 3  # 4 - 1 = 3 (promoted)

    def test_demoted_has_negative_delta(self) -> None:
        """A doc that goes from rank 1 to rank 4 has delta = 1-4=-3 < 0."""
        reranker = MockReranker(
            custom_scores={"A": 0.1, "B": 0.5, "C": 0.7, "D": 0.9}
        )
        results = reranker.rerank("query", _candidates())
        a_result = next(r for r in results if r.chunk_id == "A")
        assert a_result.rank_delta < 0  # demoted

    def test_unchanged_has_zero_delta(self) -> None:
        """If ranking order doesn't change, all deltas are 0."""
        # In alphabetical tie-break, score ordering matches initial ranking
        reranker = MockReranker(
            custom_scores={"A": 0.9, "B": 0.7, "C": 0.5, "D": 0.3}
        )
        results = reranker.rerank("query", _candidates())
        for r in results:
            assert r.rank_delta == 0


# ---------------------------------------------------------------------------
# top_k truncation
# ---------------------------------------------------------------------------

class TestTopKTruncation:
    def test_top_k_limits_reranked_output(self) -> None:
        reranker = MockReranker()
        results = reranker.rerank("query", _candidates(), top_k=2)
        assert len(results) == 2

    def test_top_k_none_returns_all(self) -> None:
        reranker = MockReranker()
        results = reranker.rerank("query", _candidates(), top_k=None)
        assert len(results) == len(_candidates())

    def test_default_top_k_applied(self) -> None:
        reranker = MockReranker(default_top_k=2)
        results = reranker.rerank("query", _candidates())
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_candidates_returns_empty(self) -> None:
        reranker = MockReranker()
        assert reranker.rerank("query", []) == []

    def test_empty_query_raises(self) -> None:
        reranker = MockReranker()
        with pytest.raises(ValueError):
            reranker.rerank("", _candidates())

    def test_whitespace_query_raises(self) -> None:
        reranker = MockReranker()
        with pytest.raises(ValueError):
            reranker.rerank("   ", _candidates())

    def test_single_candidate(self) -> None:
        reranker = MockReranker()
        result = reranker.rerank("test", [_make_result("X", 0.5, 1)])
        assert len(result) == 1
        assert result[0].chunk_id == "X"
        assert result[0].retrieval_rank == 1
        assert result[0].reranked_rank == 1
        assert result[0].rank_delta == 0


# ---------------------------------------------------------------------------
# Reranker protocol check
# ---------------------------------------------------------------------------

class TestRerankerProtocol:
    def test_mock_reranker_satisfies_protocol(self) -> None:
        reranker = MockReranker()
        assert isinstance(reranker, Reranker)


# ---------------------------------------------------------------------------
# Overlap scoring
# ---------------------------------------------------------------------------

class TestMockScoringLogic:
    def test_exact_query_phrase_gets_bonus(self) -> None:
        """Chunk containing exact query phrase scores higher than token overlap only."""
        exact_phrase = "what is the authentication policy"
        reranker = MockReranker()

        phrase_chunk = _make_result("phrase_chunk", 0.5, 1, content=exact_phrase)
        keyword_chunk = _make_result("keyword_chunk", 0.5, 2, content="authentication policy exists")

        results = reranker.rerank(exact_phrase, [phrase_chunk, keyword_chunk])
        phrase_score = next(r.reranker_score for r in results if r.chunk_id == "phrase_chunk")
        keyword_score = next(r.reranker_score for r in results if r.chunk_id == "keyword_chunk")

        assert phrase_score > keyword_score

    def test_scores_bounded_between_0_and_1(self) -> None:
        reranker = MockReranker()
        results = reranker.rerank("some query tokens", _candidates())
        for r in results:
            assert 0.0 <= r.reranker_score <= 1.0

    def test_set_custom_scores_updates(self) -> None:
        reranker = MockReranker(custom_scores={"A": 0.5})
        reranker.set_custom_scores({"A": 0.99})
        result = reranker.rerank("query", [_make_result("A", 0.5, 1)])
        assert result[0].reranker_score == pytest.approx(0.99)
