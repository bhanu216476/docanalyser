# DocAnalyser RAG Service

This is the Python-based RAG service for DocAnalyser. It handles document processing, embeddings, vector search, and LLM orchestration.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

## Embedding Pipeline

Documents flow through `Document -> Chunk -> Embedding -> EmbeddedChunk`. Each `EmbeddedChunk` keeps the original chunk text, metadata, and deterministic `chunk_id` attached to its vector. This one-to-one mapping ensures future vector-store results can be traced back to the exact document, page, heading, and source metadata used to create them.

## Chunking

The RAG service provides three modular document chunking strategies:

1. **Fixed-size chunking (`fixed`)** slices documents using configurable character lengths and overlap.
2. **Recursive character chunking (`recursive`)** uses hierarchical separators to respect paragraph, line, word, and character boundaries.
3. **Semantic chunking (`semantic`)** groups sentence and paragraph units using cosine distance between injected embedding vectors.

All strategies preserve source metadata and add deterministic chunk tracking fields including `chunk_id`, `chunk_index`, `total_chunks`, `chunking_strategy`, and `page_numbers`.

## Dense Retrieval

Dense retrieval accepts a query vector and candidate vectors from the embedding pipeline. The storage-independent pipeline is:

`metadata filters -> cosine similarity -> descending ranking -> top-k -> score threshold -> provenance extraction`

Optional metadata filters support `document_id`, `file_type`, `source`, and 1-based `page_number`. Multiple supplied fields use AND semantics; candidates missing a requested field do not match. A page filter matches `page_number`, a member of `page_numbers`, or the equivalent zero-based `page` value.

The optional score threshold is inclusive (`score >= score_threshold`) and must be a finite numeric value. It is applied after top-k, preserving the existing retrieval contract and deterministic tie-breaking.

Each retrieval result preserves the candidate `chunk_id`, content, full metadata, similarity score, and rank. It also exposes extracted provenance when available: `document_id`, `chunk_id`, page fields, headings, source, and file type. The threshold is configurable because an appropriate minimum similarity depends on the embedding model and document collection; no single value is universally correct.

## BM25 Retrieval

BM25 is a sparse lexical ranking method. It scores chunks using query-term frequency, document frequency, and document length, so exact terminology and rare technical words receive strong signals without an embedding model.

`BM25Retriever` indexes the canonical `Chunk` model in memory:

`Chunk[] -> tokenize -> BM25 index -> query tokens -> filtered scores -> RetrievalResult[]`

The tokenizer lowercases text and keeps deterministic word and number tokens. Indexing validates non-empty content and unique chunk IDs, and calling `index()` again rebuilds the index. Retrieval validates the query and `top_k`, applies the same metadata filters as the in-memory dense service, and preserves chunk metadata and typed provenance without mutating the source chunk.

Dense retrieval is useful when the query and source use different wording or when semantic similarity matters. BM25 is useful for exact names, identifiers, rare terminology, and auditable lexical matches. Both strategies return the shared `RetrievalResult` contract and operate over the same canonical chunks, which makes them suitable inputs for a future hybrid or reciprocal-rank-fusion (RRF) stage. Hybrid/RRF is not implemented yet.

## Context Builder

Final `RerankedResult` objects flow through `ContextBuilder` into a
`StructuredContext` for a future prompt/LLM layer. The context builder
preserves evidence order, content, and provenance, creates deterministic
citations, and does not perform retrieval, reranking, summarization, or
answer generation.

## Dense vs BM25 Evaluation

The comparison helper in `app/retrieval/benchmark.py` evaluates both strategies on the same `EmbeddedChunk` corpus and deterministic query cases. `run_synthetic_benchmark()` provides a small academic-style dataset, while `format_comparison()` renders aggregate Hit Rate@K, Recall@K, MRR@K, and average latency. Results are experimental: they depend on the corpus, query set, embedding model, hardware, and configuration; neither strategy is universally better.

Run the focused tests from the service directory:

```bash
python -m pytest tests/retrieval/test_bm25_index.py tests/retrieval/test_bm25_math_and_reference.py tests/retrieval/test_bm25_retriever.py tests/retrieval/test_bm25_tokenizer.py -q
python -m pytest tests/test_retrieval.py tests/retrieval/test_benchmark.py -q
```

The comparison utility can be called from a test or evaluation script with `compare_dense_and_bm25(...)`, passing the same candidates and query cases to both retrievers. For a quick local report:

```bash
python -c "from app.retrieval.benchmark import format_comparison, run_synthetic_benchmark; print(format_comparison(run_synthetic_benchmark()))"
```

