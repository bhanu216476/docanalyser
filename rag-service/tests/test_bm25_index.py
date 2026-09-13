"""Unit tests for BM25 inverted index, corpus statistics, and scoring dynamics."""

from __future__ import annotations

import pytest

from app.retrieval.bm25_index import BM25Index
from app.retrieval.exceptions import RetrievalIndexError


class TestBM25Index:
    """Test suite for BM25 inverted index and mathematical components."""

    def test_corpus_statistics(self) -> None:
        """Corpus statistics (N, avgdl, total_tokens, df, tf) are accurately maintained."""
        chunks = [
            {"chunk_id": "c1", "content": "casual leave policy"},  # 3 tokens
            {"chunk_id": "c2", "content": "sick leave and casual leave"},  # 5 tokens
        ]
        index = BM25Index()
        index.index_chunks(chunks)

        assert index.num_documents == 2
        assert index.total_tokens == 8
        assert index.avgdl == 4.0
        assert index.get_df("leave") == 2
        assert index.get_df("casual") == 2
        assert index.get_df("policy") == 1
        assert index.get_df("sick") == 1
        assert index.get_df("unknown") == 0

        assert index.get_tf("leave", 0) == 1
        assert index.get_tf("leave", 1) == 2
        assert index.get_tf("policy", 1) == 0

    def test_tf_saturation_behavior(self) -> None:
        """
        Verify that BM25 term frequency demonstrates saturation.
        As TF increases (1 -> 2 -> 5 -> 10), score growth slows sub-linearly.
        """
        # Create identical-length documents with varying TF of target term 'audit'
        # Total tokens = 10 for all docs to isolate TF saturation from length normalization
        docs = [
            {"chunk_id": "tf1", "content": "audit filler filler filler filler filler filler filler filler filler"},
            {"chunk_id": "tf2", "content": "audit audit filler filler filler filler filler filler filler filler"},
            {"chunk_id": "tf5", "content": "audit audit audit audit audit filler filler filler filler filler"},
            {"chunk_id": "tf10", "content": "audit audit audit audit audit audit audit audit audit audit"},
        ]
        index = BM25Index()
        index.index_chunks(docs)

        score_1 = index.score_document(0, ["audit"], k1=1.2, b=0.75)
        score_2 = index.score_document(1, ["audit"], k1=1.2, b=0.75)
        score_5 = index.score_document(2, ["audit"], k1=1.2, b=0.75)
        score_10 = index.score_document(3, ["audit"], k1=1.2, b=0.75)

        # Monotonically increasing
        assert score_1 < score_2 < score_5 < score_10

        # Sub-linear saturation: score does not double when TF doubles
        assert score_2 < 2 * score_1
        assert score_10 < 10 * score_1
        assert (score_10 - score_5) < (score_5 - score_1)

    def test_idf_rarity_weighting(self) -> None:
        """Rarer terms receive higher IDF scores than common terms."""
        # 10 documents: 'rare' in 1 doc, 'medium' in 3 docs, 'common' in 8 docs, 'all' in 10 docs
        chunks = []
        for i in range(10):
            content_parts = ["word", "all"]
            if i < 8:
                content_parts.append("common")
            if i < 3:
                content_parts.append("medium")
            if i == 0:
                content_parts.append("rare")
            chunks.append({"chunk_id": f"c{i}", "content": " ".join(content_parts)})

        index = BM25Index()
        index.index_chunks(chunks)

        idf_rare = index.idf("rare")
        idf_medium = index.idf("medium")
        idf_common = index.idf("common")
        idf_all = index.idf("all")
        idf_unknown = index.idf("nonexistent")

        assert idf_rare > idf_medium > idf_common > idf_all > 0.0
        # Unknown term returns 0.0
        assert idf_unknown == 0.0

    def test_document_length_normalization(self) -> None:
        """
        Verify that document length influences score according to parameter b:
        - Concise documents with the term score higher than bloated documents (b > 0).
        - When b = 0, document length does not affect score.
        """
        # Both documents have exactly 1 occurrence of 'bonus'
        short_doc = {"chunk_id": "short", "content": "bonus eligible"}  # 2 tokens
        long_doc = {
            "chunk_id": "long",
            "content": "bonus " + "unrelated " * 20,  # 21 tokens
        }

        index = BM25Index()
        index.index_chunks([short_doc, long_doc])

        # Standard b = 0.75: short document scores higher than long document
        score_short = index.score_document(0, ["bonus"], k1=1.2, b=0.75)
        score_long = index.score_document(1, ["bonus"], k1=1.2, b=0.75)
        assert score_short > score_long

        # Disabled length normalization b = 0.0: scores are identical
        score_short_b0 = index.score_document(0, ["bonus"], k1=1.2, b=0.0)
        score_long_b0 = index.score_document(1, ["bonus"], k1=1.2, b=0.0)
        assert pytest.approx(score_short_b0, rel=1e-6) == score_long_b0

        # Full length normalization b = 1.0: penalty is even more severe
        score_long_b1 = index.score_document(1, ["bonus"], k1=1.2, b=1.0)
        assert score_long_b1 < score_long

    def test_empty_corpus(self) -> None:
        """Empty corpus operations execute safely without division by zero."""
        index = BM25Index()
        assert index.num_documents == 0
        assert index.avgdl == 0.0
        assert index.idf("anything") == 0.0
        assert index.score_document(0, ["test"]) == 0.0
        assert index.search(["test"]) == []

    def test_single_document_corpus(self) -> None:
        """Single document corpus calculates valid non-negative IDF and score."""
        index = BM25Index()
        index.index_chunks([{"chunk_id": "c1", "content": "solitary document"}])

        assert index.num_documents == 1
        assert index.idf("solitary") > 0.0
        score = index.score_document(0, ["solitary"])
        assert score > 0.0

    def test_invalid_chunk_raises_error(self) -> None:
        """Indexing chunk with missing chunk_id raises RetrievalIndexError."""
        index = BM25Index()
        with pytest.raises(RetrievalIndexError):
            index.index_chunks([{"chunk_id": "", "content": "valid content"}])
