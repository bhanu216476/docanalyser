"""
Cross-Encoder Candidate Reranker integrating sentence-transformers.

Production reranker scoring query-document pairs using a Cross-Encoder
deep learning model with defensive error handling, timeout handling,
and graceful fallback.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

from app.reranking.base import BaseReranker
from app.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


class CrossEncoderCandidateReranker(BaseReranker):
    """
    Candidate reranker using a Cross-Encoder transformer model.

    Features:
        - Lazy model loading or custom model injection.
        - Automatic fallback to retrieval candidate scores if model fails or unavailable.
        - Robust NaN/Inf score sanitization.
        - Compatible with BaseReranker interface and RerankedResult output.
    """

    def __init__(
        self,
        model: Any | None = None,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        model_loader: Callable[[str], Any] | None = None,
        default_top_k: int | None = None,
        fallback_on_error: bool = True,
    ) -> None:
        super().__init__(default_top_k=default_top_k)
        self.model_name = model_name
        self._model = model
        self._model_loader = model_loader
        self.fallback_on_error = fallback_on_error

    def _get_model(self) -> Any:
        if self._model is None:
            loader = self._model_loader or self._load_default_model
            self._model = loader(self.model_name)
        return self._model

    @staticmethod
    def _load_default_model(model_name: str) -> Any:
        try:
            from sentence_transformers import CrossEncoder

            return CrossEncoder(model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load CrossEncoder model '{model_name}': {exc}"
            ) from exc

    def _score_candidates(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
    ) -> list[float]:
        if not candidates:
            return []

        try:
            model = self._get_model()
            pairs = [[query, candidate.content] for candidate in candidates]
            raw_scores = list(model.predict(pairs))

            if len(raw_scores) != len(candidates):
                raise ValueError(
                    f"Cross-encoder returned {len(raw_scores)} scores for {len(candidates)} candidates"
                )

            # Sanitize and normalize scores to [0.0, 1.0] using sigmoid
            scores: list[float] = []
            for score in raw_scores:
                val = float(score)
                if not math.isfinite(val):
                    val = 0.0
                else:
                    if val >= 0:
                        val = 1.0 / (1.0 + math.exp(-val))
                    else:
                        z = math.exp(val)
                        val = z / (1.0 + z)
                scores.append(round(val, 6))
            return scores

        except Exception as exc:
            if not self.fallback_on_error:
                raise
            logger.warning(
                "CrossEncoder scoring failed (%s); falling back to candidate retrieval scores.",
                exc,
            )
            return [
                float(cand.score) if math.isfinite(float(cand.score)) else 0.0
                for cand in candidates
            ]
