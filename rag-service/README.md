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
