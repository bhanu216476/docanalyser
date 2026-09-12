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
