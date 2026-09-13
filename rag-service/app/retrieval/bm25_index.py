"""
In-memory BM25 Inverted Index and Corpus Statistics.

Maintains:
    - N: total number of indexed document chunks
    - Document lengths |D| and avgdl (average document length)
    - Inverted index: term -> list of (doc_index, tf)
    - Document frequencies df(t)
    - Stored chunk metadata and attributes for RetrievalResult projection

IDF formulation:
    IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
Guarantees IDF(t) >= 0 for all terms, eliminating negative IDF values.
"""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Optional, Sequence

from app.retrieval.exceptions import RetrievalIndexError
from app.retrieval.tokenizer import BM25Tokenizer, tokenize


class IndexedChunkRecord:
    """Internal record of an indexed chunk in the BM25 corpus."""

    __slots__ = (
        "chunk_id",
        "content",
        "doc_len",
        "tf_map",
        "metadata",
        "document_id",
        "chunk_index",
        "file_name",
        "file_type",
        "source",
        "section",
        "start_char",
        "end_char",
    )

    def __init__(
        self,
        chunk_id: str,
        content: str,
        doc_len: int,
        tf_map: dict[str, int],
        metadata: dict[str, Any],
        document_id: str = "",
        chunk_index: Optional[int] = None,
        file_name: str = "",
        file_type: str = "",
        source: str = "",
        section: Optional[str] = None,
        start_char: Optional[int] = None,
        end_char: Optional[int] = None,
    ) -> None:
        self.chunk_id = chunk_id
        self.content = content
        self.doc_len = doc_len
        self.tf_map = tf_map
        self.metadata = metadata
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.file_name = file_name
        self.file_type = file_type
        self.source = source
        self.section = section
        self.start_char = start_char
        self.end_char = end_char


class BM25Index:
    """
    BM25 Inverted Index over a collection of document chunks.

    Maintains corpus statistics (N, avgdl, df, tf) and provides scoring
    functions parameterized by k1 (term saturation) and b (length normalization).
    """

    def __init__(
        self,
        tokenizer: Optional[BM25Tokenizer] = None,
    ) -> None:
        self._tokenizer = tokenizer or BM25Tokenizer()
        self._records: list[IndexedChunkRecord] = []
        self._chunk_id_to_idx: dict[str, int] = {}
        # Inverted index: term -> list of (doc_idx, tf)
        self._inverted_index: dict[str, list[tuple[int, int]]] = {}
        # Document frequency: term -> number of docs containing term
        self._df: dict[str, int] = {}
        self._total_tokens: int = 0
        self._avgdl: float = 0.0

    @property
    def num_documents(self) -> int:
        """Total number of indexed chunks (N)."""
        return len(self._records)

    @property
    def avgdl(self) -> float:
        """Average document length across the indexed corpus."""
        return self._avgdl

    @property
    def total_tokens(self) -> int:
        """Total token count across all indexed chunks."""
        return self._total_tokens

    def get_document_length(self, doc_idx: int) -> int:
        """Return token length |D| of document at index doc_idx."""
        if 0 <= doc_idx < len(self._records):
            return self._records[doc_idx].doc_len
        raise IndexError(f"Document index {doc_idx} out of range (0..{len(self._records)-1})")

    def get_df(self, term: str) -> int:
        """Return document frequency df(t) for term."""
        return self._df.get(term, 0)

    def get_tf(self, term: str, doc_idx: int) -> int:
        """Return term frequency TF(t, D) for term in document at doc_idx."""
        if 0 <= doc_idx < len(self._records):
            return self._records[doc_idx].tf_map.get(term, 0)
        return 0

    def get_record(self, doc_idx: int) -> IndexedChunkRecord:
        """Retrieve indexed chunk record by document index."""
        return self._records[doc_idx]

    def idf(self, term: str) -> float:
        """
        Calculate BM25 Robertson-Spärck Jones Inverse Document Frequency (IDF) with +1 smoothing:

            IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

        Edge cases:
            - Term not in corpus (df == 0) or empty corpus (N == 0): returns 0.0
            - Term in all documents (df == N): strictly positive (> 0.0)
        """
        n = self.num_documents
        df = self.get_df(term)
        if n == 0 or df <= 0:
            return 0.0

        numerator = n - df + 0.5
        denominator = df + 0.5
        ratio = 1.0 + (numerator / denominator)
        if ratio <= 0.0:
            return 0.0
        return math.log(ratio)

    def index_chunks(self, chunks: Sequence[Any]) -> None:
        """
        Index a sequence of chunks into the BM25 inverted index.

        Accepts:
            - Chunk instances (app.ingestion.chunking.models or app.chunking.models)
            - EmbeddedChunk instances (app.embeddings.models)
            - LangChain Document instances
            - Dictionaries with 'chunk_id', 'content', 'metadata', etc.

        Raises:
            RetrievalIndexError: If chunk structure is invalid.
        """
        for chunk in chunks:
            self._add_single_chunk(chunk)

        if self._records:
            self._avgdl = self._total_tokens / len(self._records)
        else:
            self._avgdl = 0.0

    def _add_single_chunk(self, chunk: Any) -> None:
        """Extract attributes, tokenize, update inverted index and corpus statistics."""
        data = self._extract_chunk_attributes(chunk)
        chunk_id = data["chunk_id"]

        if not chunk_id:
            raise RetrievalIndexError("Cannot index chunk with empty chunk_id")

        tokens = self._tokenizer.tokenize(data["content"])
        doc_len = len(tokens)
        tf_counts = Counter(tokens)

        doc_idx = len(self._records)
        self._chunk_id_to_idx[chunk_id] = doc_idx

        record = IndexedChunkRecord(
            chunk_id=chunk_id,
            content=data["content"],
            doc_len=doc_len,
            tf_map=dict(tf_counts),
            metadata=data["metadata"],
            document_id=data["document_id"],
            chunk_index=data["chunk_index"],
            file_name=data["file_name"],
            file_type=data["file_type"],
            source=data["source"],
            section=data["section"],
            start_char=data["start_char"],
            end_char=data["end_char"],
        )
        self._records.append(record)
        self._total_tokens += doc_len

        # Update inverted index and document frequencies
        for term, tf in tf_counts.items():
            if term not in self._inverted_index:
                self._inverted_index[term] = []
                self._df[term] = 0
            self._inverted_index[term].append((doc_idx, tf))
            self._df[term] += 1

    def _extract_chunk_attributes(self, chunk: Any) -> dict[str, Any]:
        """Extract canonical attributes from various supported chunk representations."""
        if isinstance(chunk, dict):
            metadata = dict(chunk.get("metadata", {}))
            return {
                "chunk_id": str(chunk.get("chunk_id", "") or metadata.get("chunk_id", "")),
                "content": str(chunk.get("content", "") or chunk.get("page_content", "") or chunk.get("text", "")),
                "document_id": str(chunk.get("document_id", "") or metadata.get("document_id", "")),
                "chunk_index": chunk.get("chunk_index", metadata.get("chunk_index")),
                "file_name": str(chunk.get("file_name", "") or metadata.get("file_name", "")),
                "file_type": str(chunk.get("file_type", "") or metadata.get("file_type", "")),
                "source": str(chunk.get("source", "") or metadata.get("source", "")),
                "section": chunk.get("section", metadata.get("section")),
                "start_char": chunk.get("start_char", metadata.get("start_char")),
                "end_char": chunk.get("end_char", metadata.get("end_char")),
                "metadata": metadata,
            }

        # Object representation (Chunk, EmbeddedChunk, Document)
        chunk_id = getattr(chunk, "chunk_id", None)
        content = getattr(chunk, "content", None) or getattr(chunk, "page_content", None) or getattr(chunk, "text", "")
        metadata = dict(getattr(chunk, "metadata", {}) or {})

        if not chunk_id:
            chunk_id = metadata.get("chunk_id", "")

        document_id = getattr(chunk, "document_id", "") or metadata.get("document_id", "")
        chunk_index = getattr(chunk, "chunk_index", None)
        if chunk_index is None:
            chunk_index = metadata.get("chunk_index")

        file_name = getattr(chunk, "file_name", "") or metadata.get("file_name", "")
        file_type = getattr(chunk, "file_type", "") or metadata.get("file_type", "")
        source = getattr(chunk, "source", "") or metadata.get("source", "")
        section = getattr(chunk, "section", None) or metadata.get("section")
        start_char = getattr(chunk, "start_char", None) or metadata.get("start_char")
        end_char = getattr(chunk, "end_char", None) or metadata.get("end_char")

        return {
            "chunk_id": str(chunk_id),
            "content": str(content),
            "document_id": str(document_id),
            "chunk_index": chunk_index,
            "file_name": str(file_name),
            "file_type": str(file_type),
            "source": str(source),
            "section": section,
            "start_char": start_char,
            "end_char": end_char,
            "metadata": metadata,
        }

    def score_document(
        self,
        doc_idx: int,
        query_terms: Sequence[str],
        k1: float = 1.2,
        b: float = 0.75,
    ) -> float:
        """
        Calculate BM25 score for a single document against query terms:

            BM25(D, Q) = sum_{q in Q} IDF(q) * [ TF(q, D) * (k1 + 1) ] / [ TF(q, D) + k1 * (1 - b + b * |D| / avgdl) ]

        Args:
            doc_idx: Document index in records.
            query_terms: Sequence of tokenized query terms.
            k1: Term frequency saturation parameter (>= 0).
            b: Length normalization parameter (0 <= b <= 1).

        Returns:
            Computed raw BM25 score (float >= 0.0).
        """
        if not (0 <= doc_idx < len(self._records)) or not query_terms or self.num_documents == 0:
            return 0.0

        record = self._records[doc_idx]
        doc_len = record.doc_len
        avgdl = self._avgdl if self._avgdl > 0.0 else 1.0

        len_norm = 1.0 - b + (b * (doc_len / avgdl))
        score = 0.0

        for term in query_terms:
            tf = record.tf_map.get(term, 0)
            if tf <= 0:
                continue

            idf_val = self.idf(term)
            if idf_val <= 0.0:
                continue

            tf_component = (tf * (k1 + 1.0)) / (tf + (k1 * len_norm))
            score += idf_val * tf_component

        return score

    def search(
        self,
        query_terms: Sequence[str],
        eligible_indices: Optional[set[int]] = None,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> list[tuple[int, float]]:
        """
        Search inverted index for matching documents and return raw BM25 scores.

        Args:
            query_terms: Tokenized query terms.
            eligible_indices: Optional pre-filtered set of document indices allowed to match.
            k1: BM25 saturation parameter.
            b: BM25 length normalization parameter.

        Returns:
            List of (doc_idx, score) for documents with score > 0.0.
        """
        if not query_terms or self.num_documents == 0:
            return []

        avgdl = self._avgdl if self._avgdl > 0.0 else 1.0

        # Accumulator: doc_idx -> score
        scores: dict[int, float] = {}

        # Query terms can have repeats, but each unique term's IDF is weighted once per occurrence in query,
        # or we iterate term by term. Standard BM25 sums over terms q in query.
        for term in query_terms:
            idf_val = self.idf(term)
            if idf_val <= 0.0:
                continue

            postings = self._inverted_index.get(term, [])
            for doc_idx, tf in postings:
                if eligible_indices is not None and doc_idx not in eligible_indices:
                    continue

                record = self._records[doc_idx]
                len_norm = 1.0 - b + (b * (record.doc_len / avgdl))
                tf_component = (tf * (k1 + 1.0)) / (tf + (k1 * len_norm))
                term_score = idf_val * tf_component

                scores[doc_idx] = scores.get(doc_idx, 0.0) + term_score

        return [(doc_idx, s) for doc_idx, s in scores.items() if s > 0.0]
