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
