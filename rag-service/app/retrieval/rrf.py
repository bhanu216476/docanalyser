"""
Reciprocal Rank Fusion (RRF) core algorithm.

Combines multiple ranked retrieval result sets into a single unified hybrid
ranking using rank positions rather than incompatible raw similarity scores:

    RRF(d) = Σ [ 1 / (k + r_i(d)) ]

Where:
    d:        document / chunk identifier
    r_i(d):   1-based rank of document d in retrieval system i
    k:        ranking smoothing constant (default: 60)

Key properties:
    - 1-based ranks (rank 1 is highest relevance).
    - Absent documents in a ranking contribute 0.0 (no artificial penalty).
    - Multi-source support: works with arbitrary M >= 1 ranking lists.
    - Per-source deduplication: duplicate chunk IDs within a single list retain
      their best (lowest 1-based rank) position.
    - Deterministic tie-breaking: (-rrf_score, chunk_id).
    - Preserves chunk content, metadata, provenance, and source-level rank breakdown.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Optional

from app.core.config import settings
from app.retrieval.models import HybridRetrievalResult, RetrievalResult

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RetrievalResult]] | Mapping[str, Sequence[RetrievalResult]],
    k: int = 60,
    top_k: Optional[int] = None,
) -> list[HybridRetrievalResult]:
    """
    Execute Reciprocal Rank Fusion over multiple ranked result sets.

    Args:
        rankings: Either a sequence of result lists or a mapping of
                  {source_name: result_list} (e.g. {"dense": [...], "bm25": [...]}).
        k:        Ranking constant parameter (k > 0). Defaults to 60.
        top_k:    Optional maximum number of hybrid results to return.
                  If None, returns all unique fused candidates.

    Returns:
        List of HybridRetrievalResult sorted descending by fused RRF score,
        with deterministic tie-breaking on chunk_id.

    Raises:
        ValueError: If k <= 0 or top_k <= 0.
    """
    if k <= 0:
        raise ValueError(f"RRF parameter k must be a positive integer, got {k}")
    if top_k is not None and top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k}")

    # Standardize input into a sequence of (source_name, result_list)
    named_rankings: list[tuple[str, Sequence[RetrievalResult]]]
    if isinstance(rankings, Mapping):
        named_rankings = list(rankings.items())
    else:
        named_rankings = [
            (f"source_{i}", result_list)
            for i, result_list in enumerate(rankings)
        ]

    # Track scores, metadata, and per-source rank positions
    scores: dict[str, float] = {}
    candidate_map: dict[str, RetrievalResult] = {}
    source_ranks: dict[str, dict[str, int]] = {}

    for source_name, result_list in named_rankings:
        seen_in_source: set[str] = set()

        for idx, result in enumerate(result_list):
            chunk_id = result.chunk_id
            if chunk_id in seen_in_source:
                # Deduplicate within this source: keep first/best rank
                continue
            seen_in_source.add(chunk_id)

            # 1-based rank calculation
            rank_1based = idx + 1
            contribution = 1.0 / (k + rank_1based)

            scores[chunk_id] = scores.get(chunk_id, 0.0) + contribution

            if chunk_id not in candidate_map:
                candidate_map[chunk_id] = result
                source_ranks[chunk_id] = {}

            source_ranks[chunk_id][source_name] = rank_1based

    if not scores:
        return []

    # Deterministic sorting: primary key is -rrf_score, secondary is chunk_id
    sorted_chunk_ids = sorted(
        scores.keys(),
        key=lambda cid: (-scores[cid], cid),
    )

    if top_k is not None:
        sorted_chunk_ids = sorted_chunk_ids[:top_k]

    results: list[HybridRetrievalResult] = []
    for final_rank, chunk_id in enumerate(sorted_chunk_ids, start=1):
        source_candidate = candidate_map[chunk_id]
        sr = source_ranks.get(chunk_id, {})

        results.append(
            HybridRetrievalResult(
                chunk_id=chunk_id,
                content=source_candidate.content,
                score=scores[chunk_id],
                rrf_score=scores[chunk_id],
                rank=final_rank,
                metadata=dict(source_candidate.metadata),
                document_id=source_candidate.document_id,
                chunk_index=source_candidate.chunk_index,
                file_name=source_candidate.file_name,
                file_type=source_candidate.file_type,
                source=source_candidate.source,
                section=source_candidate.section,
                start_char=source_candidate.start_char,
                end_char=source_candidate.end_char,
                provenance=source_candidate.provenance,
                dense_rank=sr.get("dense"),
                bm25_rank=sr.get("bm25"),
                source_ranks=dict(sr),
            )
        )

    return results
