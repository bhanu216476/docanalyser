"""Lazy, dependency-injected cross-encoder reranking."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.retrieval.models import RetrievalResult
from app.retrieval.reranker import _validate_top_k, _with_score


class CrossEncoderReranker:
    """Score query-document pairs with an injected or lazily loaded model."""

    def __init__(
        self,
        model: Any | None = None,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        model_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self._model = model
        self._model_loader = model_loader

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        _validate_top_k(top_k)
        if not candidates:
            return []

        model = self._get_model()
        pairs = [[query, candidate.content] for candidate in candidates]
        scores = list(model.predict(pairs))
        if len(scores) != len(candidates):
            raise ValueError(
                "cross-encoder returned a different number of scores than candidates"
            )

        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: (-float(item[1]), item[0].chunk_id),
        )[:top_k]
        return [
            _with_score(candidate, float(score), rank)
            for rank, (candidate, score) in enumerate(ranked, start=1)
        ]

    def _get_model(self) -> Any:
        if self._model is None:
            loader = self._model_loader or _load_sentence_transformer_cross_encoder
            self._model = loader(self.model_name)
        return self._model


def _load_sentence_transformer_cross_encoder(model_name: str) -> Any:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required to load a CrossEncoder model; "
            "inject a model or model_loader for offline use"
        ) from exc
    return CrossEncoder(model_name)