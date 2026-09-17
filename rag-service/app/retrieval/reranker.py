"""Reranker abstractions and deterministic test-friendly implementations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.retrieval.models import RetrievalResult


class Reranker(Protocol):
    """Protocol for query-aware candidate reranking."""

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    """Return candidates in their existing order without external services."""

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        _validate_top_k(top_k)
        return [
            _with_score(candidate, candidate.score, rank)
            for rank, candidate in enumerate(candidates[:top_k], start=1)
        ]


def _with_score(result: RetrievalResult, score: float, rank: int) -> RetrievalResult:
    data = result.model_dump()
    data.update(score=float(score), rank=rank)
    return RetrievalResult.model_validate(data)


def _validate_top_k(top_k: int) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}")