# Dense Retrieval Service

**Day 8 — DocAnalyser RAG Service**

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│   EmbeddingService  │  ← embed_texts([query])
│  (existing service) │
└──────────┬──────────┘
           │
           ▼
     Query Vector
  (same model/dim as
   stored embeddings)
           │
           ▼
┌─────────────────────┐
│   Qdrant Collection │  ← similarity search
│   Vector Search     │     with optional filter
└──────────┬──────────┘
           │
           ▼
    ScoredPoint[]
    (Qdrant native)
           │
           ▼
┌─────────────────────┐
│   DenseRetriever    │  ← payload mapping
│   _map_scored_point │
└──────────┬──────────┘
           │
           ▼
    RetrievalResult[]
```

The retrieval layer sits between the embedding service and future RAG
orchestration (LLM generation, reranking, citation rendering).

---

## Retrieval Flow (Example)

```
Query: "How many casual leave days?"

    ↓  strip + validate

    ↓  EmbeddingService.embed_texts(["How many casual leave days?"])
       → [0.12, 0.45, -0.31, …]  (1536-dim for text-embedding-3-small)

    ↓  Qdrant.search(collection="documents", query_vector=[…], limit=10)
       + optional metadata filter (push-down to Qdrant)

    ↓

Result 1 → score: 0.91  chunk_id="hr-doc:2"  "Casual leave is 10 days per year."
Result 2 → score: 0.87  chunk_id="hr-doc:0"  "Annual leave is 20 days per year."
Result 3 → score: 0.83  chunk_id="hr-doc:5"  "Leave entitlements vary by grade."
...
```

---

## Retriever Protocol

The `Retriever` protocol (in `app/retrieval/retriever.py`) is a structural
`typing.Protocol` that all retrieval strategies must satisfy:

```python
class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievalResult]: ...
```

Future implementations (not in scope today):
- `BM25Retriever` — keyword sparse retrieval
- `HybridRetriever` — RRF fusion of dense + sparse
- `RerankedRetriever` — wraps any Retriever with cross-encoder reranking

---

## Configuration

All settings are read from environment variables (via Pydantic Settings).
Defaults are suitable for local development.

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_API_KEY` | `""` | Optional Qdrant API key (never logged) |
| `QDRANT_COLLECTION_NAME` | `documents` | Collection to search |
| `QDRANT_VECTOR_SIZE` | `1536` | Embedding dimension (must match collection) |
| `QDRANT_DISTANCE` | `Cosine` | Distance metric (Cosine, Dot, Euclid) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model identifier |
| `OPENAI_API_KEY` | `""` | OpenAI key (empty = FakeEmbeddingProvider) |
| `RETRIEVAL_DEFAULT_TOP_K` | `10` | Default top-K if not specified per request |
| `RETRIEVAL_MAX_TOP_K` | `100` | Hard upper bound — requests above this are rejected |

---

## Request Model: `RetrievalRequest`

```python
class RetrievalRequest(BaseModel):
    query: str              # Non-empty after whitespace stripping
    top_k: int = 10         # 1 ≤ top_k ≤ RETRIEVAL_MAX_TOP_K
    filters: RetrievalFilter | None = None
```

### Validation rules

| Field | Rule |
|---|---|
| `query` | Stripped of surrounding whitespace. Rejected if empty after stripping. |
| `top_k` | Must be `>= 1`. Must be `<= RETRIEVAL_MAX_TOP_K`. Default `10`. |
| `filters` | All filter fields optional; multiple fields combined with AND. |

---

## Filter Model: `RetrievalFilter`

```python
class RetrievalFilter(BaseModel):
    document_id: str | list[str] | None  # Single or list of document IDs
    file_type:   str | list[str] | None  # e.g. "md", "txt", or ["md", "txt"]
    source:      str | None              # Exact normalized source path
    chunk_index: int | None              # Exact 0-based chunk index
    file_name:   str | None              # Source file basename
    section:     str | None              # Markdown section heading
```

Filters are **pushed down to Qdrant** using indexed payload fields.
No Python-side filtering is performed after retrieval.

Multiple specified fields are combined with **logical AND** in Qdrant.

---

## Result Model: `RetrievalResult`

```python
class RetrievalResult(BaseModel):
    chunk_id:    str            # Original deterministic chunk identifier
    score:       float          # Qdrant similarity score (see Score Semantics)
    document_id: str            # Source document identifier
    chunk_index: int            # 0-based sequential chunk index
    content:     str            # Chunk text (stored in Qdrant payload)
    file_name:   str            # Source document basename
    file_type:   str            # File extension ('md', 'txt', etc.)
    source:      str            # Normalized source path
    section:     str | None     # Markdown section heading
    start_char:  int | None     # Start character offset in source
    end_char:    int | None     # End character offset in source
    metadata:    dict           # Additional custom metadata
```

---

## Similarity Score Semantics

| Distance metric | Score range | Interpretation |
|---|---|---|
| **Cosine** (default) | `[-1.0, 1.0]` | `1.0` = identical direction |
| **Dot** | Unbounded | Higher = more similar |
| **Euclid** | `≤ 0` (negated) | Closer to `0` = more similar |
| **Manhattan** | `≤ 0` (negated) | Closer to `0` = more similar |

Results are returned in **Qdrant's native ranking order** (highest score first).
The retrieval layer does **not** re-sort results.

---

## API Endpoint

### `POST /api/retrieval/dense`

Execute a dense vector similarity search.

**Request body:**
```json
{
  "query": "How many casual leave days?",
  "top_k": 10
}
```

**Request with filter:**
```json
{
  "query": "How many casual leave days?",
  "top_k": 5,
  "filters": {
    "document_id": "hr-policy-doc-123"
  }
}
```

**Response (200 OK):**
```json
[
  {
    "chunk_id": "hr-policy-doc-123:2",
    "score": 0.91,
    "document_id": "hr-policy-doc-123",
    "chunk_index": 2,
    "content": "Casual leave is limited to 10 days per year.",
    "file_name": "hr_policy.md",
    "file_type": "md",
    "source": "docs/hr_policy.md",
    "section": "Leave Policy",
    "start_char": 450,
    "end_char": 512,
    "metadata": {}
  },
  ...
]
```

**Error responses:**

| HTTP Status | Condition |
|---|---|
| `422 Unprocessable Entity` | Invalid query (empty) or invalid top_k |
| `503 Service Unavailable` | Embedding service or Qdrant unavailable |
| `500 Internal Server Error` | Unexpected error |

---

## Error Handling

The service distinguishes three failure categories with separate exceptions:

### 1. `RetrievalQueryError` (non-retryable)
- Empty or whitespace-only query
- `top_k <= 0`
- `top_k > RETRIEVAL_MAX_TOP_K`

**Behavior:** Immediately raises `HTTP 422`. Do not retry — fix the input.

### 2. `RetrievalEmbeddingError`
- Embedding provider unavailable or timed out (`is_transient=True`)
- Authentication failure (`is_transient=False`)
- Invalid embedding vector returned
- Vector dimension mismatch between embedding and collection

**Behavior:** Raises `HTTP 503`. Transient errors may be retried by the caller.

### 3. `RetrievalQdrantError`
- Qdrant service unavailable / connection refused (`is_transient=True`)
- Qdrant returns 5xx HTTP error (`is_transient=True`)
- Collection does not exist (`is_transient=False`)
- Authentication/configuration failure (`is_transient=False`)

**Behavior:** Raises `HTTP 503`. Transient errors may be retried.

### Empty Result (not an error)
When Qdrant finds no matching chunks, `retrieve()` returns `[]` (empty list)
with HTTP `200 OK`. This is **not** an error — it means no documents matched
the query (or the filter is too restrictive).

```python
results = retriever.retrieve("obscure query with no match")
# → []   ← not an exception
```

---

## Code Location

```
app/retrieval/
├── __init__.py          # Public API exports
├── exceptions.py        # RetrievalError hierarchy
├── models.py            # RetrievalFilter, RetrievalRequest, RetrievalResult
├── retriever.py         # Retriever protocol (typing.Protocol)
└── dense_retriever.py   # DenseRetriever + create_dense_retriever factory

app/api/
└── retrieval.py         # FastAPI router: POST /api/retrieval/dense

tests/
├── test_retrieval_models.py       # Pydantic validation unit tests
├── test_dense_retriever.py        # DenseRetriever unit tests (mocked)
└── test_retrieval_integration.py  # End-to-end tests (in-memory Qdrant)
```

---

## Running Tests

```bash
cd rag-service
.venv/Scripts/activate  # Windows

# Unit tests only (no external services)
pytest tests/test_retrieval_models.py tests/test_dense_retriever.py -v

# Integration tests (in-memory Qdrant — no Docker needed)
pytest tests/test_retrieval_integration.py -v -m integration

# All tests
pytest tests/ -v
```

---

## What Is NOT In Scope (Day 8)

- BM25 / keyword retrieval
- Hybrid retrieval (RRF fusion)
- Reranking (cross-encoder)
- LLM answer generation
- Prompt construction
- Conversational memory
- Citation rendering
- Agentic retrieval
