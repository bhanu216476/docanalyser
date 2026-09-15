"""
Deterministic Mock Reranker for offline testing and benchmarking.

Computes reproducible scores without requiring external model weights,
GPU hardware, or third-party APIs. Supports custom score mappings
for explicit unit test assertions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
import time
from typing import Optional

from app.retrieval.models import RetrievalResult
from app.reranking.base import BaseReranker


class MockReranker(BaseReranker):
    """
    Deterministic mock reranker.

    Scoring logic:
        1. If a chunk_id is present in `custom_scores`, that exact float is used.
        2. Otherwise, a normalized score in [0.0, 1.0] is derived from token
           overlap and exact phrase containment:
               score = 0.7 * (intersection / len(query_terms)) + 0.3 * phrase_bonus
    """

    def __init__(
        self,
        custom_scores: Optional[Mapping[str, float]] = None,
        default_top_k: Optional[int] = None,
        simulated_delay_ms: float = 0.0,
    ) -> None:
        super().__init__(default_top_k=default_top_k)
        self.custom_scores = dict(custom_scores) if custom_scores is not None else {}
        self.simulated_delay_ms = max(0.0, simulated_delay_ms)

    def set_custom_scores(self, scores: Mapping[str, float]) -> None:
        """Update or replace custom score assignments."""
        self.custom_scores = dict(scores)

    def _score_candidates(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
    ) -> list[float]:
        if self.simulated_delay_ms > 0:
            time.sleep(self.simulated_delay_ms / 1000.0)

        query_tokens = set(re.findall(r"\b\w+\b", query.lower()))
        scores: list[float] = []

        for cand in candidates:
            if cand.chunk_id in self.custom_scores:
                scores.append(float(self.custom_scores[cand.chunk_id]))
                continue

            content_lower = cand.content.lower()
            cand_tokens = set(re.findall(r"\b\w+\b", content_lower))

            if not query_tokens:
                scores.append(0.0)
                continue

            overlap_count = len(query_tokens.intersection(cand_tokens))
            overlap_ratio = overlap_count / len(query_tokens)

            phrase_bonus = 0.3 if query.lower() in content_lower else 0.0
            base_score = 0.7 * overlap_ratio + phrase_bonus

            scores.append(round(min(1.0, base_score), 4))

        return scores
