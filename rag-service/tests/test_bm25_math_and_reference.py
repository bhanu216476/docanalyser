"""
Unit tests comparing BM25 implementation against analytical hand calculations
and a standalone independent reference implementation.
"""

from __future__ import annotations

import math
import pytest

from app.retrieval.bm25_index import BM25Index
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.tokenizer import tokenize


def reference_bm25_okapi(
    corpus: list[str],
    query: str,
    k1: float = 1.2,
    b: float = 0.75,
) -> list[float]:
    """
    Independent reference BM25 implementation for cross-verification.
    Computes Okapi BM25 with Robertson-Spärck Jones +1 smoothed IDF.
    """
    tokenized_corpus = [tokenize(doc) for doc in corpus]
    query_tokens = tokenize(query)
    n = len(corpus)

    if n == 0:
        return []

    doc_lengths = [len(doc) for doc in tokenized_corpus]
    avgdl = sum(doc_lengths) / n if n > 0 else 1.0

    # Calculate DF
    df: dict[str, int] = {}
    for doc in tokenized_corpus:
        unique_terms = set(doc)
        for t in unique_terms:
            df[t] = df.get(t, 0) + 1

    # Calculate IDF
    idf: dict[str, float] = {}
    for t in set(query_tokens):
        t_df = df.get(t, 0)
        if t_df == 0:
            idf[t] = 0.0
        else:
            idf[t] = math.log(1.0 + (n - t_df + 0.5) / (t_df + 0.5))

    scores: list[float] = []
    for doc, doc_len in zip(tokenized_corpus, doc_lengths):
        score = 0.0
        len_norm = 1.0 - b + (b * (doc_len / avgdl))
        for t in query_tokens:
            tf = doc.count(t)
            if tf > 0 and idf.get(t, 0.0) > 0.0:
                tf_comp = (tf * (k1 + 1.0)) / (tf + (k1 * len_norm))
                score += idf[t] * tf_comp
        scores.append(score)

    return scores


class TestBM25MathAndReference:
    """Verification against analytical hand calculations and reference formulation."""

    def test_hand_calculated_example(self) -> None:
        """
        Verify exact analytical match for the worked example from docs/retrieval/bm25.md:
            Chunk A: "Employees receive casual leave every year."
            Chunk B: "Employees receive annual leave and sick leave."
            Chunk C: "Office parking policy and vehicle regulations."
            Query: "casual leave"
        """
        chunks = [
            {"chunk_id": "chunk_a", "content": "Employees receive casual leave every year."},
            {"chunk_id": "chunk_b", "content": "Employees receive annual leave and sick leave."},
            {"chunk_id": "chunk_c", "content": "Office parking policy and vehicle regulations."},
        ]

        index = BM25Index()
        index.index_chunks(chunks)

        # 1. Verify lengths and avgdl
        assert index.get_document_length(0) == 6
        assert index.get_document_length(1) == 7
        assert index.get_document_length(2) == 6
        assert pytest.approx(index.avgdl, rel=1e-6) == 19.0 / 3.0

        # 2. Verify exact analytical IDFs
        expected_idf_casual = math.log(1.0 + (3.0 - 1.0 + 0.5) / (1.0 + 0.5))  # ln(8/3)
        expected_idf_leave = math.log(1.0 + (3.0 - 2.0 + 0.5) / (2.0 + 0.5))   # ln(8/5)

        assert pytest.approx(index.idf("casual"), rel=1e-6) == expected_idf_casual
        assert pytest.approx(index.idf("leave"), rel=1e-6) == expected_idf_leave

        # 3. Verify analytical BM25 scores
        # Chunk A:
        len_norm_a = 1.0 - 0.75 + (0.75 * (6.0 / (19.0 / 3.0)))
        tf_comp_casual_a = (1.0 * 2.2) / (1.0 + 1.2 * len_norm_a)
        tf_comp_leave_a = (1.0 * 2.2) / (1.0 + 1.2 * len_norm_a)
        expected_score_a = (expected_idf_casual * tf_comp_casual_a) + (expected_idf_leave * tf_comp_leave_a)

        score_a = index.score_document(0, ["casual", "leave"], k1=1.2, b=0.75)
        assert pytest.approx(score_a, rel=1e-5) == expected_score_a
        assert pytest.approx(score_a, rel=1e-3) == 1.482758

        # Chunk B:
        len_norm_b = 1.0 - 0.75 + (0.75 * (7.0 / (19.0 / 3.0)))
        tf_comp_leave_b = (2.0 * 2.2) / (2.0 + 1.2 * len_norm_b)
        expected_score_b = expected_idf_leave * tf_comp_leave_b

        score_b = index.score_document(1, ["casual", "leave"], k1=1.2, b=0.75)
        assert pytest.approx(score_b, rel=1e-5) == expected_score_b
        assert pytest.approx(score_b, rel=1e-3) == 0.627673

        # Chunk C:
        score_c = index.score_document(2, ["casual", "leave"], k1=1.2, b=0.75)
        assert score_c == 0.0

        # Ranking check
        assert score_a > score_b > score_c

    def test_cross_comparison_with_reference_implementation(self) -> None:
        """
        Compare BM25Index search output across a multi-document corpus
        against the independent reference implementation.
        """
        raw_corpus = [
            "Data ingestion and indexing with Elasticsearch and BM25",
            "Dense vector embeddings using OpenAI and sentence transformers",
            "Hybrid retrieval fusing dense vector and lexical BM25 results",
            "PostgreSQL relational document metadata storage and JSON payloads",
            "Retrieval-Augmented Generation RAG pipelines with LLM generation",
        ]
        chunks = [{"chunk_id": f"c_{i}", "content": text} for i, text in enumerate(raw_corpus)]

        index = BM25Index()
        index.index_chunks(chunks)

        queries = [
            "BM25 lexical retrieval",
            "OpenAI vector embeddings",
            "PostgreSQL metadata",
            "hybrid RAG pipelines",
        ]

        for q in queries:
            ref_scores = reference_bm25_okapi(raw_corpus, q, k1=1.2, b=0.75)
            q_terms = tokenize(q)
            for idx in range(len(raw_corpus)):
                actual_score = index.score_document(idx, q_terms, k1=1.2, b=0.75)
                assert pytest.approx(actual_score, rel=1e-5) == ref_scores[idx]
