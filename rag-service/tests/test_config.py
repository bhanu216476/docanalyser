from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "field",
    [
        "hybrid_dense_top_k",
        "hybrid_bm25_top_k",
        "hybrid_candidate_top_k",
        "hybrid_rrf_k",
        "rerank_candidate_top_k",
        "rerank_top_k",
    ],
)
def test_hybrid_and_reranking_values_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: 0})


def test_rerank_top_k_cannot_exceed_candidates() -> None:
    with pytest.raises(ValidationError):
        Settings(rerank_candidate_top_k=2, rerank_top_k=3)


def test_hybrid_candidate_top_k_cannot_exceed_source_capacity() -> None:
    with pytest.raises(ValidationError):
        Settings(hybrid_dense_top_k=1, hybrid_bm25_top_k=1, hybrid_candidate_top_k=3)