from __future__ import annotations

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import RetrievalResult


def result(chunk_id: str, score: float = 0.5, content: str | None = None) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=content or f"content for {chunk_id}",
        score=score,
        document_id="document-1",
        file_name="source.md",
        metadata={"tag": chunk_id},
    )


def test_fuses_scores_from_both_ranked_lists_and_starts_ranks_at_one() -> None:
    dense = [result("a"), result("b"), result("c")]
    bm25 = [result("b"), result("c"), result("d")]

    fused = reciprocal_rank_fusion([dense, bm25], rrf_k=60, top_k=4)

    assert [item.chunk_id for item in fused] == ["b", "c", "a", "d"]
    assert [item.rank for item in fused] == [1, 2, 3, 4]
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert fused[1].score == pytest.approx(1 / 63 + 1 / 62)


def test_preserves_first_result_metadata_without_mutating_inputs() -> None:
    dense = [result("same", score=0.9, content="dense content")]
    bm25 = [result("same", score=3.0, content="bm25 content")]

    fused = reciprocal_rank_fusion([dense, bm25], rrf_k=10)

    assert fused[0].content == "dense content"
    assert fused[0].metadata == {"tag": "same"}
    assert fused[0].score == pytest.approx(2 / 11)
    assert dense[0].score == 0.9
    assert bm25[0].score == 3.0


def test_ties_use_chunk_id_and_candidate_limit() -> None:
    fused = reciprocal_rank_fusion(
        [[result("z")], [result("a")], [result("m")]],
        rrf_k=60,
        top_k=2,
    )

    assert [item.chunk_id for item in fused] == ["a", "m"]


@pytest.mark.parametrize("ranked_lists", [[], [[], []]])
def test_empty_ranked_lists_return_empty(ranked_lists: list[list[RetrievalResult]]) -> None:
    assert reciprocal_rank_fusion(ranked_lists) == []


def test_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], rrf_k=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], top_k=0)