"""Deterministic dense-versus-BM25 evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

from app.chunking.models import Chunk
from app.embeddings.models import EmbeddedChunk
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.models import RetrievalResult
from app.retrieval.service import DenseRetrievalService


@dataclass(frozen=True)
class BenchmarkQuery:
    """One query evaluated against the same dense and BM25 corpus."""

    query: str
    relevant_chunk_ids: frozenset[str]
    dense_query_vector: tuple[float, ...]


@dataclass(frozen=True)
class QueryComparison:
    query: str
    relevant_chunk_ids: frozenset[str]
    dense_results: tuple[RetrievalResult, ...]
    bm25_results: tuple[RetrievalResult, ...]
    dense_latency_ms: float
    bm25_latency_ms: float


@dataclass(frozen=True)
class RetrievalMetrics:
    hit_rate_at_k: float
    recall_at_k: float
    mrr_at_k: float
    average_latency_ms: float


@dataclass(frozen=True)
class BenchmarkComparison:
    queries: tuple[QueryComparison, ...]
    dense: RetrievalMetrics
    bm25: RetrievalMetrics


def run_synthetic_benchmark(*, top_k: int = 1) -> BenchmarkComparison:
    """Run a small deterministic academic-style comparison dataset."""
    chunks = [
        Chunk(
            chunk_id="bm25-chunk",
            content="BM25 lexical retrieval ranks rare technical terms.",
            chunk_index=0,
            chunking_strategy="fixed",
            document_id="retrieval-doc",
        ),
        Chunk(
            chunk_id="dense-chunk",
            content="Semantic vector retrieval captures meaning across wording.",
            chunk_index=1,
            chunking_strategy="fixed",
            document_id="retrieval-doc",
        ),
        Chunk(
            chunk_id="timetable-chunk",
            content="University timetabling uses optimization constraints.",
            chunk_index=0,
            chunking_strategy="fixed",
            document_id="optimization-doc",
        ),
    ]
    vectors = ((1.0, 0.0), (0.0, 1.0), (0.2, 0.98))
    dense_candidates = [
        EmbeddedChunk(
            index=index,
            embedding=list(vector),
            token_count=1,
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            metadata={"document_id": chunk.document_id},
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    bm25 = BM25Retriever()
    bm25.index_chunks(chunks)
    queries = [
        BenchmarkQuery(
            query="BM25 lexical retrieval",
            relevant_chunk_ids=frozenset({"bm25-chunk"}),
            dense_query_vector=(1.0, 0.0),
        ),
        BenchmarkQuery(
            query="meaning across wording",
            relevant_chunk_ids=frozenset({"dense-chunk"}),
            dense_query_vector=(0.0, 1.0),
        ),
        BenchmarkQuery(
            query="university timetabling optimization",
            relevant_chunk_ids=frozenset({"timetable-chunk"}),
            dense_query_vector=(0.2, 0.98),
        ),
    ]
    return compare_dense_and_bm25(
        DenseRetrievalService(),
        bm25,
        dense_candidates,
        queries,
        top_k=top_k,
    )


def format_comparison(comparison: BenchmarkComparison) -> str:
    """Format aggregate comparison metrics as a compact Markdown table."""
    rows = [
        ("Hit Rate@K", comparison.dense.hit_rate_at_k, comparison.bm25.hit_rate_at_k),
        ("Recall@K", comparison.dense.recall_at_k, comparison.bm25.recall_at_k),
        ("MRR@K", comparison.dense.mrr_at_k, comparison.bm25.mrr_at_k),
        (
            "Avg latency (ms)",
            comparison.dense.average_latency_ms,
            comparison.bm25.average_latency_ms,
        ),
    ]
    lines = ["| Metric | Dense Search | BM25 |", "|---|---:|---:|"]
    lines.extend(
        f"| {label} | {dense:.4f} | {bm25:.4f} |"
        for label, dense, bm25 in rows
    )
    return "\n".join(lines)


def compare_dense_and_bm25(
    dense_service: DenseRetrievalService,
    bm25_retriever: BM25Retriever,
    dense_candidates: Sequence[EmbeddedChunk],
    queries: Sequence[BenchmarkQuery],
    *,
    top_k: int = 5,
) -> BenchmarkComparison:
    """Evaluate both retrievers on one corpus and one deterministic query set."""
    comparisons: list[QueryComparison] = []

    for case in queries:
        dense_start = perf_counter()
        dense_results = dense_service.retrieve(
            case.dense_query_vector, dense_candidates, top_k=top_k
        )
        dense_latency_ms = (perf_counter() - dense_start) * 1000

        bm25_start = perf_counter()
        bm25_results = bm25_retriever.retrieve(case.query, top_k=top_k)
        bm25_latency_ms = (perf_counter() - bm25_start) * 1000

        comparisons.append(
            QueryComparison(
                query=case.query,
                relevant_chunk_ids=case.relevant_chunk_ids,
                dense_results=tuple(dense_results),
                bm25_results=tuple(bm25_results),
                dense_latency_ms=dense_latency_ms,
                bm25_latency_ms=bm25_latency_ms,
            )
        )

    return BenchmarkComparison(
        queries=tuple(comparisons),
        dense=_metrics(comparisons, "dense"),
        bm25=_metrics(comparisons, "bm25"),
    )


def _metrics(
    comparisons: Sequence[QueryComparison], strategy: str
) -> RetrievalMetrics:
    if not comparisons:
        raise ValueError("queries cannot be empty")

    hits = 0
    recall_total = 0.0
    reciprocal_rank_total = 0.0
    latency_total = 0.0

    for comparison in comparisons:
        results = getattr(comparison, f"{strategy}_results")
        result_ids = [result.chunk_id for result in results]
        relevant = comparison.relevant_chunk_ids
        if not relevant:
            raise ValueError("each query must define at least one relevant chunk")
        retrieved_relevant = set(result_ids) & relevant
        hits += bool(retrieved_relevant)
        recall_total += len(retrieved_relevant) / len(relevant)
        for rank, chunk_id in enumerate(result_ids, start=1):
            if chunk_id in relevant:
                reciprocal_rank_total += 1 / rank
                break
        latency_total += getattr(comparison, f"{strategy}_latency_ms")

    count = len(comparisons)
    return RetrievalMetrics(
        hit_rate_at_k=hits / count,
        recall_at_k=recall_total / count,
        mrr_at_k=reciprocal_rank_total / count,
        average_latency_ms=latency_total / count,
    )
