"""
BM25 Lexical Retrieval implementation.

Pipeline position:
    User Query
        │
    BM25Retriever.retrieve()
        │
    Tokenize query (BM25Tokenizer)
        │
    Pre-filter eligible candidate chunk indices
        │
    BM25 Scoring (BM25Index)
        │
    Deterministic tie-breaking (-score, chunk_id)
        │
    Top-K truncation
        │
    RetrievalResult[]

Conforms to the Retriever protocol (app.retrieval.retriever.Retriever).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence

from app.core.config import settings
from app.retrieval.bm25_index import BM25Index
from app.retrieval.exceptions import RetrievalIndexError, RetrievalQueryError
from app.retrieval.models import RetrievalFilter, RetrievalRequest, RetrievalResult
from app.retrieval.tokenizer import BM25Tokenizer, tokenize

logger = logging.getLogger(__name__)


class BM25Retriever:
    """
    Lexical retrieval strategy using BM25 scoring over an indexed chunk corpus.

    Conforms structurally to the ``Retriever`` protocol.

    Args:
        index: Configured BM25Index instance.
        k1: Term frequency saturation parameter (>= 0).
        b: Document length normalization parameter (0 <= b <= 1).
        max_top_k: Hard upper bound on top_k results.
        tokenizer: BM25Tokenizer instance for query preprocessing.
    """

    def __init__(
        self,
        index: Optional[BM25Index] = None,
        k1: Optional[float] = None,
        b: Optional[float] = None,
        max_top_k: Optional[int] = None,
        tokenizer: Optional[BM25Tokenizer] = None,
    ) -> None:
        self.index = index if index is not None else BM25Index()
        self.k1 = k1 if k1 is not None else settings.bm25_k1
        self.b = b if b is not None else settings.bm25_b
        self.max_top_k = max_top_k if max_top_k is not None else settings.bm25_max_top_k
        self.tokenizer = tokenizer or BM25Tokenizer()

        self._validate_parameters(self.k1, self.b, self.max_top_k)

        logger.info(
            "BM25Retriever initialized: k1=%.2f, b=%.2f, max_top_k=%d, corpus_size=%d",
            self.k1,
            self.b,
            self.max_top_k,
            self.index.num_documents,
        )

    # -----------------------------------------------------------------------
    # Public API — conforms to Retriever protocol
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        """
        Execute BM25 lexical retrieval and return ranked results.

        Flow:
            query -> validate -> tokenize -> pre-filter eligible -> BM25 score
                  -> deterministic sort (-score, chunk_id) -> top_k -> RetrievalResult[]

        Args:
            query: User search query string (must be non-empty after stripping).
            top_k: Maximum number of results to return (1 <= top_k <= max_top_k).
            filters: Optional metadata filters applied before ranking.

        Returns:
            List of RetrievalResult ordered by descending BM25 score.
            Returns an empty list [] when no chunks match or corpus is empty.

        Raises:
            RetrievalQueryError: On invalid query or top_k.
            RetrievalIndexError: On unexpected index failure.
        """
        t_start = time.monotonic()

        validated_query = self._validate_query(query)
        validated_top_k = self._validate_top_k(top_k)

        if self.index.num_documents == 0:
            logger.info("BM25 retrieval on empty corpus: returning []")
            return []

        query_terms = self.tokenizer.tokenize(validated_query)
        if not query_terms:
            logger.info("BM25 query produced no tokens after preprocessing: returning []")
            return []

        # 1. Pre-filter candidate documents based on metadata filter
        eligible_indices = self._filter_eligible_indices(filters)
        if eligible_indices is not None and len(eligible_indices) == 0:
            logger.info("BM25 retrieval: filter matched 0 chunks; returning []")
            return []

        # 2. Score candidate documents via BM25 inverted index
        try:
            scored_candidates = self.index.search(
                query_terms=query_terms,
                eligible_indices=eligible_indices,
                k1=self.k1,
                b=self.b,
            )
        except Exception as exc:
            logger.exception("BM25 index search failed: %s", exc)
            raise RetrievalIndexError(f"BM25 search failed: {exc}") from exc

        if not scored_candidates:
            logger.info("BM25 retrieval: no positive-scoring chunks found")
            return []

        # 3. Deterministic tie-breaking: primary key -score, secondary key chunk_id
        # We look up chunk_id for each doc_idx to sort stably
        enriched_candidates = [
            (doc_idx, score, self.index.get_record(doc_idx).chunk_id)
            for doc_idx, score in scored_candidates
        ]
        enriched_candidates.sort(key=lambda item: (-item[1], item[2]))

        # 4. Truncate to top_k
        selected = enriched_candidates[:validated_top_k]

        # 5. Map to standard RetrievalResult models
        results: list[RetrievalResult] = []
        for rank, (doc_idx, score, _) in enumerate(selected, start=1):
            record = self.index.get_record(doc_idx)
            results.append(
                RetrievalResult(
                    chunk_id=record.chunk_id,
                    content=record.content,
                    score=float(score),
                    rank=rank,
                    metadata=dict(record.metadata),
                    document_id=record.document_id,
                    chunk_index=record.chunk_index,
                    file_name=record.file_name,
                    file_type=record.file_type,
                    source=record.source,
                    section=record.section,
                    start_char=record.start_char,
                    end_char=record.end_char,
                )
            )

        elapsed_ms = (time.monotonic() - t_start) * 1000
        logger.info(
            "BM25 retrieval finished: returned %d results for top_k=%d in %.2f ms",
            len(results),
            validated_top_k,
            elapsed_ms,
        )

        return results

    def retrieve_from_request(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Convenience method accepting a validated RetrievalRequest."""
        return self.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )

    def index_chunks(self, chunks: Sequence[Any]) -> None:
        """Index chunks into the internal BM25 index."""
        self.index.index_chunks(chunks)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _validate_parameters(self, k1: float, b: float, max_top_k: int) -> None:
        if k1 < 0.0:
            raise ValueError(f"k1 must be >= 0.0 (got {k1})")
        if not (0.0 <= b <= 1.0):
            raise ValueError(f"b must be between 0.0 and 1.0 (got {b})")
        if max_top_k <= 0:
            raise ValueError(f"max_top_k must be > 0 (got {max_top_k})")

    def _validate_query(self, query: str) -> str:
        if not isinstance(query, str):
            raise RetrievalQueryError("query must be a string")
        stripped = query.strip()
        if not stripped:
            raise RetrievalQueryError("query cannot be empty or whitespace-only")
        return stripped

    def _validate_top_k(self, top_k: int) -> int:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise RetrievalQueryError(f"top_k must be a positive integer >= 1, got {top_k!r}")
        if top_k > self.max_top_k:
            raise RetrievalQueryError(
                f"top_k={top_k} exceeds the maximum allowed value of {self.max_top_k}"
            )
        return top_k

    def _filter_eligible_indices(
        self,
        filters: Optional[RetrievalFilter],
    ) -> Optional[set[int]]:
        """
        Evaluate metadata filter against all indexed chunks before scoring.

        Returns:
            Set of document indices eligible for scoring, or None if no filters.
        """
        if filters is None or filters.is_empty:
            return None

        eligible: set[int] = set()
        doc_id_set = (
            {filters.document_id}
            if isinstance(filters.document_id, str)
            else set(filters.document_id)
            if filters.document_id is not None
            else None
        )
        file_type_set = (
            {filters.file_type.lower()}
            if isinstance(filters.file_type, str)
            else {ft.lower() for ft in filters.file_type}
            if filters.file_type is not None
            else None
        )

        for doc_idx in range(self.index.num_documents):
            rec = self.index.get_record(doc_idx)

            if doc_id_set is not None and rec.document_id not in doc_id_set:
                continue
            if file_type_set is not None and rec.file_type.lower() not in file_type_set:
                continue
            if filters.source is not None and rec.source != filters.source:
                continue
            if filters.chunk_index is not None and rec.chunk_index != filters.chunk_index:
                continue
            if filters.file_name is not None and rec.file_name != filters.file_name:
                continue
            if filters.section is not None and rec.section != filters.section:
                continue

            eligible.add(doc_idx)

        return eligible


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def create_bm25_retriever(
    chunks: Optional[Sequence[Any]] = None,
    k1: Optional[float] = None,
    b: Optional[float] = None,
    max_top_k: Optional[int] = None,
) -> BM25Retriever:
    """
    Factory creating a BM25Retriever, optionally pre-populating with chunks.

    Args:
        chunks: Optional initial chunk sequence to index.
        k1: BM25 saturation parameter. Defaults to settings.bm25_k1.
        b: BM25 length normalization parameter. Defaults to settings.bm25_b.
        max_top_k: Maximum top_k allowed. Defaults to settings.bm25_max_top_k.

    Returns:
        Configured BM25Retriever instance.
    """
    index = BM25Index()
    if chunks:
        index.index_chunks(chunks)

    return BM25Retriever(
        index=index,
        k1=k1,
        b=b,
        max_top_k=max_top_k,
    )
