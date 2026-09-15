"""Reciprocal Rank Fusion for retrieval results."""

from __future__ import annotations

from collections.abc import Sequence

from app.retrieval.models import RetrievalResult


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[RetrievalResult]],
    *,
    rrf_k: int = 60,
    top_k: int | None = None,
) -> list[RetrievalResult]:
    """Fuse ranked result lists using standard Reciprocal Rank Fusion.

    Results are identified by ``chunk_id``. The first result encountered for
    an id supplies its content and metadata; all occurrences contribute to its
    fused score. Fused results are rebuilt so frozen input models are never
    mutated.
    """
    _validate_positive_int(rrf_k, "rrf_k")
    if top_k is not None:
        _validate_positive_int(top_k, "top_k")

    scores: dict[str, float] = {}
    source_results: dict[str, RetrievalResult] = {}
    for ranked_results in ranked_lists:
        for rank, result in enumerate(ranked_results, start=1):
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            source_results.setdefault(chunk_id, result)

    ordered_chunk_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    if top_k is not None:
        ordered_chunk_ids = ordered_chunk_ids[:top_k]

    return [
        _with_fused_score(source_results[chunk_id], scores[chunk_id], rank)
        for rank, chunk_id in enumerate(ordered_chunk_ids, start=1)
    ]


def _with_fused_score(
    result: RetrievalResult,
    score: float,
    rank: int,
) -> RetrievalResult:
    data = result.model_dump()
    data.update(score=score, rank=rank)
    return RetrievalResult.model_validate(data)


def _validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")