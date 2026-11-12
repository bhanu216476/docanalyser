"""
Tests for Adaptive Hybrid Retrieval in DocAnalyser.
"""

from app.retrieval.adaptive import (
    compute_token_jaccard,
    deduplicate_chunks,
    filter_by_relevance_floor,
    normalize_bm25_score,
    normalize_dense_score,
)
from app.retrieval.models import RetrievalResult


def test_score_normalization():
    # Dense cosine [-1, 1] -> [0, 1]
    assert normalize_dense_score(1.0) == 1.0
    assert normalize_dense_score(0.0) == 0.5
    assert normalize_dense_score(-1.0) == 0.0

    # BM25 [0, inf) -> [0, 1]
    assert normalize_bm25_score(0.0) == 0.0
    bm25_norm = normalize_bm25_score(12.5)
    assert 0.0 < bm25_norm <= 1.0


def test_chunk_deduplication():
    chunk_1 = RetrievalResult(
        chunk_id="doc1_chunk_0",
        document_id="doc1",
        content="DocAnalyser uses hybrid retrieval combining dense vector search and sparse BM25 indexing.",
        score=0.95,
        rank=1,
    )
    # Near-duplicate overlapping chunk from the same document
    chunk_2 = RetrievalResult(
        chunk_id="doc1_chunk_1",
        document_id="doc1",
        content="DocAnalyser uses hybrid retrieval combining dense vector search and sparse BM25 indexing with RRF.",
        score=0.88,
        rank=2,
    )
    # Different chunk from doc2
    chunk_3 = RetrievalResult(
        chunk_id="doc2_chunk_0",
        document_id="doc2",
        content="PostgreSQL persists user accounts and document lifecycle records in production.",
        score=0.80,
        rank=3,
    )

    candidates = [chunk_1, chunk_2, chunk_3]
    deduped = deduplicate_chunks(candidates, similarity_threshold=0.70)

    # Chunk 2 should be dropped due to high overlap with chunk 1
    assert len(deduped) == 2
    assert deduped[0].chunk_id == "doc1_chunk_0"
    assert deduped[1].chunk_id == "doc2_chunk_0"


def test_relevance_floor_filtering():
    c1 = RetrievalResult(chunk_id="c1", document_id="d1", content="Text 1", score=10.0, rank=1)
    c2 = RetrievalResult(chunk_id="c2", document_id="d1", content="Text 2", score=9.0, rank=2)
    c3 = RetrievalResult(chunk_id="c3", document_id="d1", content="Text 3", score=8.5, rank=3)
    c4 = RetrievalResult(chunk_id="c4", document_id="d1", content="Text 4", score=0.5, rank=4)  # Noise

    filtered = filter_by_relevance_floor([c1, c2, c3, c4], min_score_percentile=0.20, min_results=2)
    assert len(filtered) == 3
    assert all(c.score >= 2.0 for c in filtered)
