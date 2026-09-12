"""In-memory dense retrieval over embedded chunks."""

from __future__ import annotations

from collections.abc import Sequence
import math
from numbers import Real

from app.embeddings.models import EmbeddedChunk
from app.embeddings.service import EmbeddingService
from app.retrieval.models import RetrievalResult
from app.retrieval.similarity import cosine_similarity


class DenseRetrievalService:
    """Rank embedded chunks using cosine similarity."""

    def retrieve(
        self,
        query_vector: Sequence[float],
        candidates: Sequence[EmbeddedChunk],
        *,
        top_k: int = 5,
        score_threshold: Real | None = None,
    ) -> list[RetrievalResult]:
        """Return ranked candidates after top-k selection and thresholding.

        Candidates are ranked by descending score, with their original input
        position breaking ties. The threshold is inclusive and is applied
        after top-k selection.
        """
        self._validate_top_k(top_k)
        threshold = self._validate_threshold(score_threshold)

        ranked: list[tuple[int, EmbeddedChunk, float]] = []
        for input_index, candidate in enumerate(candidates):
            score = cosine_similarity(query_vector, candidate.vector)
            ranked.append((input_index, candidate, score))

        ranked.sort(key=lambda item: (-item[2], item[0]))
        selected = ranked[:top_k]
        if threshold is not None:
            selected = [item for item in selected if item[2] >= threshold]

        return [
            RetrievalResult(
                chunk_id=candidate.chunk_id,
                content=candidate.content,
                metadata=dict(candidate.metadata),
                score=score,
                rank=rank,
            )
            for rank, (_, candidate, score) in enumerate(selected, start=1)
        ]

    def retrieve_text(
        self,
        query: str,
        candidates: Sequence[EmbeddedChunk],
        embedding_service: EmbeddingService,
        *,
        top_k: int = 5,
        score_threshold: Real | None = None,
    ) -> list[RetrievalResult]:
        """Embed a text query with the existing service, then retrieve."""
        query_result = embedding_service.embed_texts([query])[0]
        return self.retrieve(
            query_result.embedding,
            candidates,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive integer, got {top_k!r}")

    @staticmethod
    def _validate_threshold(score_threshold: Real | None) -> float | None:
        if score_threshold is None:
            return None
        if isinstance(score_threshold, bool) or not isinstance(score_threshold, Real):
            raise ValueError("score_threshold must be numeric")
        threshold = float(score_threshold)
        if not math.isfinite(threshold):
            raise ValueError("score_threshold must be finite")
        return threshold
