from __future__ import annotations

import pytest

from app.retrieval.cross_encoder_reranker import CrossEncoderReranker
from app.retrieval.models import RetrievalResult
from app.retrieval.reranker import IdentityReranker


def result(chunk_id: str, score: float = 0.1) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=f"content {chunk_id}",
        score=score,
        metadata={"chunk": chunk_id},
    )


class FakeCrossEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.pairs: list[list[str]] | None = None

    def predict(self, pairs: list[list[str]]) -> list[float]:
        self.pairs = pairs
        return self.scores


def test_identity_reranker_is_deterministic_and_non_mutating() -> None:
    candidates = [result("b", 0.2), result("a", 0.1)]

    reranked = IdentityReranker().rerank("query", candidates, top_k=1)

    assert [item.chunk_id for item in reranked] == ["b"]
    assert reranked[0].rank == 1
    assert reranked[0].score == 0.2
    assert candidates[0].rank is None


def test_cross_encoder_uses_injected_model_and_preserves_fields() -> None:
    model = FakeCrossEncoder([0.2, 0.9])
    candidates = [result("b"), result("a")]

    reranked = CrossEncoderReranker(model=model).rerank("query", candidates, top_k=2)

    assert model.pairs == [["query", "content b"], ["query", "content a"]]
    assert [item.chunk_id for item in reranked] == ["a", "b"]
    assert [item.score for item in reranked] == [0.9, 0.2]
    assert reranked[0].metadata == {"chunk": "a"}
    assert candidates[0].score == 0.1


def test_cross_encoder_loads_lazily_through_injected_loader() -> None:
    model = FakeCrossEncoder([1.0])
    calls: list[str] = []

    def loader(model_name: str) -> FakeCrossEncoder:
        calls.append(model_name)
        return model

    reranker = CrossEncoderReranker(model_name="fake-model", model_loader=loader)
    assert calls == []
    reranker.rerank("query", [result("a")], top_k=1)
    assert calls == ["fake-model"]


def test_cross_encoder_rejects_score_count_mismatch_and_invalid_top_k() -> None:
    with pytest.raises(ValueError):
        CrossEncoderReranker(model=FakeCrossEncoder([])).rerank(
            "query", [result("a")], top_k=1
        )
    with pytest.raises(ValueError):
        IdentityReranker().rerank("query", [result("a")], top_k=0)