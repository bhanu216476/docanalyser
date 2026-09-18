# DocAnalyser RAG V0.1 — Demo Runbook

This runbook provides step-by-step operational instructions for starting, ingesting documents, querying, and verifying the **DocAnalyser RAG V0.1 End-to-End Pipeline**.

---

## 1. Architecture Overview

```text
Upload Document (PDF / TXT / MD)
   ↓
[PDFLoader / TxtLoader / MarkdownLoader]
   ↓
[RecursiveChunker] → Chunk[] (Deterministic UUIDs)
   ↓
[EmbeddingService] → Vector[] (1536-dim)
   ↓
┌───────────────────────┬───────────────────────┐
│                       │                       │
▼                       ▼                       │
Qdrant Vector Store   BM25 Inverted Index       │
(Dense Semantic)      (Lexical BM25)            │
│                       │                       │
└───────────┬───────────┘                       │
            ▼                                   │
     User Query (Dense + Lexical Search)        │
            ↓                                   │
  Reciprocal Rank Fusion (RRF k=60)             │
            ↓                                   │
  Candidate Reranker (Cross-Attention)          │
            ↓                                   │
  Context Builder (Deduplication + Token Budget)│
            ↓                                   │
  Prompt Builder (V1 / V2 / V3 Assembly)        │
            ↓                                   │
  LLM Provider (Generation + Grounding)         │
            ↓                                   │
  Grounded Answer + Verified Citations          │
```

---

## 2. Prerequisites

Ensure your environment satisfies the following:
- **Python**: 3.11+ (Python 3.12 verified)
- **Virtual Environment**: `.venv` activated
- **Docker & Docker Compose**: (Optional for production Qdrant/Postgres; in-memory mode works standalone)
- **Environment Variables**:
  - `OPENAI_API_KEY`: Optional; if omitted, `FakeEmbeddingProvider` and `FakeLLMProvider` provide deterministic offline execution.
  - `QDRANT_URL`: Defaults to `http://localhost:6333` (or `:memory:`).

---

## 3. Quickstart: Instant Offline Demo (Zero External Services)

To run the complete end-to-end demo immediately without starting any external Docker containers or providing API keys:

```powershell
cd "c:\Users\CH BHANU\OneDrive\Desktop\RAG base\rag-service"
.venv\Scripts\python -m app.pipeline.demo_cli
```

### What this executes:
1. Generates a synthetic multi-page PDF (`company_leave_policy.pdf`) in a temporary directory.
2. Ingests, chunks, embeds, and indexes into an in-memory Qdrant instance and BM25 index.
3. Fires 5 representative queries:
   - **Direct Factual**: "How many casual leave days do employees receive?"
   - **Second Factual**: "How many sick leave days are provided?"
   - **Procedure**: "How should leave requests be submitted?"
   - **Semantic Paraphrase**: "What is the quota for informal time off?"
   - **Refusal (Unsupported)**: "What is the company's international travel allowance?"
4. Displays formatted output with stage latencies and verified citations.

---

## 4. Production / Containerized Service Startup

### Step 1: Start Infrastructure Containers

From the repository root:
```powershell
docker-compose -f infrastructure/docker-compose.yml up -d
```
This spins up:
- **Qdrant**: `http://localhost:6333`
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

Verify Qdrant is healthy:
```powershell
curl http://localhost:6333/healthz
```

### Step 2: Start the FastAPI Service

From `rag-service`:
```powershell
cd "c:\Users\CH BHANU\OneDrive\Desktop\RAG base\rag-service"
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs will be available at:
`http://localhost:8000/docs`

---

## 5. API Usage Guide

### Ingesting a Document

#### Option A: Ingest via File Upload (Multipart Form)
```bash
curl -X POST "http://localhost:8000/api/v1/rag/ingest" \
  -F "file=@/path/to/leave_policy.pdf"
```

#### Option B: Ingest via Local File Path
```bash
curl -X POST "http://localhost:8000/api/v1/rag/ingest" \
  -F "file_path=/path/to/leave_policy.pdf"
```

**Expected Response (`201 Created`):**
```json
{
  "document_id": "e6350065b7bcef33e1f8cae65a6ecb689fb231e8af9584a7b760006c6f60374c",
  "file_name": "leave_policy.pdf",
  "file_type": "pdf",
  "chunk_count": 2,
  "latency_breakdown_ms": {
    "load_ms": 3.26,
    "chunk_ms": 0.11,
    "embed_ms": 1.32,
    "vector_store_ms": 2.28,
    "bm25_ms": 0.18,
    "total_ms": 7.15
  }
}
```

---

### Executing a Grounded Query

```bash
curl -X POST "http://localhost:8000/api/v1/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many casual leave days do employees receive?",
    "prompt_version": "v2",
    "top_k": 5
  }'
```

**Expected Response (`200 OK`):**
```json
{
  "query": "How many casual leave days do employees receive?",
  "answer": "Employees receive 12 casual leave days per calendar year for personal matters. [1]",
  "citations": [
    {
      "citation_id": "[1]",
      "chunk_id": "e6350065b7bcef33e1f8cae65a6ecb689fb231e8af9584a7b760006c6f60374c:0",
      "document_id": "e6350065b7bcef33e1f8cae65a6ecb689fb231e8af9584a7b760006c6f60374c",
      "source": "leave_policy.pdf",
      "file_name": "leave_policy.pdf",
      "file_type": "pdf",
      "page_number": 1,
      "section": null
    }
  ],
  "prompt_version": "v2",
  "latency_breakdown_ms": {
    "retrieval_ms": 2.4,
    "fusion_ms": 0.05,
    "reranking_ms": 0.2,
    "context_building_ms": 0.2,
    "prompt_assembly_ms": 0.05,
    "llm_generation_ms": 0.02,
    "total_ms": 2.92
  },
  "metadata": {
    "dense_candidates_count": 2,
    "bm25_candidates_count": 2,
    "fused_candidates_count": 2,
    "reranked_candidates_count": 2,
    "context_token_count": 142,
    "selected_chunks_count": 2,
    "dropped_chunks_count": 0
  }
}
```

---

## 6. Automated Testing

Run the full automated test suite to ensure all unit, integration, and end-to-end tests pass:

```powershell
cd "c:\Users\CH BHANU\OneDrive\Desktop\RAG base\rag-service"

# Run Day 14 specific test suites
.venv\Scripts\pytest tests/test_pdf_loader.py tests/test_rag_pipeline.py tests/test_rag_end_to_end.py tests/test_rag_api.py -v

# Run complete project test suite (580+ tests)
.venv\Scripts\pytest
```

---

## 7. Troubleshooting Guide

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| `IngestionError: Unsupported document extension` | Uploading a file type other than `.pdf`, `.txt`, `.md`. | Ensure the file extension is supported or implement a loader for that file type. |
| `IngestionError: Target file does not exist` | Invalid file path passed to `ingest()`. | Provide an absolute or valid relative path to an existing file. |
| `QdrantConnectionError` during startup | Qdrant Docker container not running on port 6333. | The pipeline will automatically fall back to `:memory:` store for local dev. To use remote Qdrant, run `docker-compose -f infrastructure/docker-compose.yml up -d qdrant`. |
| `QueryPipelineError: Query text cannot be empty` | Sending whitespace or empty query. | Validate non-empty query string prior to submission. |
| Empty citations `[]` on query response | Query was unanswerable from the context; model output a grounded refusal. | This is expected behavior for out-of-domain questions. Verify document content contains the factual answer. |
