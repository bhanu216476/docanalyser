"""
Base interface and abstractions for candidate rerankers.

Defines the structural Reranker protocol and a reusable BaseReranker providing
input validation, deterministic tie-breaking, rank-delta computation,
and high-resolution latency tracking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
import logging
import time
from typing import Optional, Protocol, runtime_checkable

from app.retrieval.models import HybridRetrievalResult, RetrievalResult
from app.reranking.models import RerankedResult

logger = logging.getLogger(__name__)


@runtime_checkable
class Reranker(Protocol):
    """
    Structural protocol satisfied by any candidate reranker.

    Enables swapping reranker implementations (mock, cross-encoder, API)
    without modifying retrieval pipelines or experiment runners.
    """

    def rerank(
        self,
        query: str,
        documents: Sequence[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RerankedResult]:
        """
        Score and reorder candidate retrieval results.

        Args:
            query: User search query string.
            documents: Candidate retrieval results from previous stage.
            top_k: Optional limit on the number of returned results.

        Returns:
            List of RerankedResult ordered by descending reranker score.
        """
        ...


class BaseReranker(ABC):
    """
    Abstract base class providing common orchestration for reranker implementations.

    Subclasses need only implement ``_score_candidates``.
    """

    def __init__(self, default_top_k: Optional[int] = None) -> None:
        self.default_top_k = default_top_k

    def rerank(
        self,
        query: str,
        documents: Sequence[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RerankedResult]:
        """
        Execute candidate reranking with validation, deterministic ordering,
        and rank-delta tracking.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        effective_top_k = top_k if top_k is not None else self.default_top_k
        if effective_top_k is not None and effective_top_k <= 0:
            raise ValueError(f"top_k must be a positive integer, got {effective_top_k}")

        if not documents:
            return []

        # Retain original 1-based initial ranks
        initial_candidates: list[tuple[int, RetrievalResult]] = []
        for idx, doc in enumerate(documents):
            init_rank = doc.rank if doc.rank is not None else (idx + 1)
            initial_candidates.append((init_rank, doc))

        # Compute reranking scores
        raw_candidates = [doc for _, doc in initial_candidates]
        scores = self._score_candidates(query.strip(), raw_candidates)

        if len(scores) != len(documents):
            raise ValueError(
                f"Scoring mismatch: expected {len(documents)} scores, got {len(scores)}"
            )

        # Build tuples: (initial_rank, candidate, reranker_score)
        scored_pairs = [
            (init_rank, doc, float(score))
            for (init_rank, doc), score in zip(initial_candidates, scores)
        ]

        # Deterministic sorting: primary key is -reranker_score, secondary is chunk_id
        scored_pairs.sort(key=lambda item: (-item[2], item[1].chunk_id))

        if effective_top_k is not None:
            scored_pairs = scored_pairs[:effective_top_k]

        reranked_results: list[RerankedResult] = []
        for new_rank, (initial_rank, doc, rerank_score) in enumerate(scored_pairs, start=1):
            rank_delta = initial_rank - new_rank

            # Extract hybrid-specific fields if available
            dense_rank = getattr(doc, "dense_rank", None)
            bm25_rank = getattr(doc, "bm25_rank", None)
            source_ranks = getattr(doc, "source_ranks", {})

            reranked_results.append(
                RerankedResult(
                    chunk_id=doc.chunk_id,
                    content=doc.content,
                    retrieval_score=float(doc.score),
                    reranker_score=rerank_score,
                    retrieval_rank=initial_rank,
                    reranked_rank=new_rank,
                    rank_delta=rank_delta,
                    metadata=dict(doc.metadata),
                    document_id=doc.document_id,
                    chunk_index=doc.chunk_index,
                    file_name=doc.file_name,
                    file_type=doc.file_type,
                    source=doc.source,
                    section=doc.section,
                    provenance=doc.provenance,
                    dense_rank=dense_rank,
                    bm25_rank=bm25_rank,
                    source_ranks=dict(source_ranks),
                )
            )

        return reranked_results

    @abstractmethod
    def _score_candidates(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
    ) -> list[float]:
        """Compute relevance scores for candidates relative to the query."""
        ...
