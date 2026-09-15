"""
RRF k-parameter experiment utility.

Evaluates how the smoothing parameter k (e.g. k=20, 40, 60, 100) influences:
    - Score distributions and compression.
    - Sensitivity to top-ranked documents vs consensus documents.
    - Resulting rank orderings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.models import RetrievalResult
from app.retrieval.rrf import reciprocal_rank_fusion


class KExperimentRecord(BaseModel):
    """Result record for a single document under a specific k value."""

    k: int = Field(..., description="RRF constant k used.")
    chunk_id: str = Field(..., description="Chunk identifier.")
    rrf_score: float = Field(..., description="Calculated RRF score.")
    rank: int = Field(..., ge=1, description="1-based rank position.")
    source_ranks: dict[str, int] = Field(
        default_factory=dict,
        description="Per-source rank contributions.",
    )

    model_config = ConfigDict(frozen=True)


def run_k_experiment(
    rankings: Sequence[Sequence[RetrievalResult]] | Mapping[str, Sequence[RetrievalResult]],
    k_values: Sequence[int] = (20, 40, 60, 100),
    top_k: Optional[int] = None,
) -> dict[int, list[KExperimentRecord]]:
    """
    Run RRF across multiple k values on the same input rankings.

    Args:
        rankings: Input rankings from multiple retrieval sources.
        k_values: Sequence of k values to evaluate (default: 20, 40, 60, 100).
        top_k: Optional truncation limit for output records per k.

    Returns:
        Mapping of {k: list[KExperimentRecord]} ordered by descending RRF score.
    """
    experiment_results: dict[int, list[KExperimentRecord]] = {}

    for k in k_values:
        fused = reciprocal_rank_fusion(rankings=rankings, k=k, top_k=top_k)
        records = [
            KExperimentRecord(
                k=k,
                chunk_id=res.chunk_id,
                rrf_score=res.rrf_score,
                rank=res.rank or (idx + 1),
                source_ranks=dict(res.source_ranks),
            )
            for idx, res in enumerate(fused)
        ]
        experiment_results[k] = records

    return experiment_results


def format_k_comparison_table(
    experiment_results: dict[int, list[KExperimentRecord]],
) -> str:
    """
    Format multi-k experiment results into a clean markdown comparison table.
    """
    k_list = sorted(experiment_results.keys())
    if not k_list:
        return "No experiment results."

    # Collect all unique chunk_ids
    all_chunk_ids: list[str] = []
    seen: set[str] = set()
    for k in k_list:
        for rec in experiment_results[k]:
            if rec.chunk_id not in seen:
                seen.add(rec.chunk_id)
                all_chunk_ids.append(rec.chunk_id)

    # Build header
    header_cols = ["Chunk ID"]
    for k in k_list:
        header_cols.extend([f"Rank (k={k})", f"RRF Score (k={k})"])
    header_line = "| " + " | ".join(header_cols) + " |"
    sep_line = "| " + " | ".join(["---"] * len(header_cols)) + " |"

    rows: list[str] = [header_line, sep_line]

    # Map each (chunk_id, k) to record
    lookup: dict[tuple[str, int], KExperimentRecord] = {}
    for k, records in experiment_results.items():
        for r in records:
            lookup[(r.chunk_id, k)] = r

    for cid in all_chunk_ids:
        row_vals = [cid]
        for k in k_list:
            rec = lookup.get((cid, k))
            if rec is not None:
                row_vals.extend([str(rec.rank), f"{rec.rrf_score:.6f}"])
            else:
                row_vals.extend(["-", "-"])
        rows.append("| " + " | ".join(row_vals) + " |")

    return "\n".join(rows)
