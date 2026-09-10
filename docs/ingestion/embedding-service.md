# Embedding Service Architecture

The Embedding Service transforms document text chunks into dense, fixed-dimensional semantic vector representations ready for indexing and retrieval in a vector store.

---

## Pipeline Position

```
Document (Loader)
      │
      ▼
Chunks (Chunking Pipeline)
      │
      ▼
EmbeddingService  ◄── [This Component]
      │
      ▼
EmbeddingResult[] (Vector + Metadata)
      │
      ▼
Future: Vector Store (Qdrant)
```

The Embedding Service sits directly between the document chunking stage and the future vector store ingestion stage. It accepts text strings or `Chunk` objects, coordinates token validation and batching, invokes an embedding provider, handles retries and errors, and outputs typed `EmbeddingResult` objects.

---

## Responsibilities & Boundaries

### Included Responsibilities
- **Batch Processing**: Groups inputs into configurable batch sizes (default: 20) to maximize provider throughput and minimize network roundtrips.
- **Token Limit Enforcement**: Validates per-item token counts upfront before any API calls are dispatched, preventing costly mid-batch token overflow errors.
- **Retry Logic & Backoff**: Retries transient provider errors (rate limits, timeouts, HTTP 5xx) with exponential backoff and randomized full jitter; permanent errors fail immediately.
- **Provider Abstraction**: Decouples embedding generation from specific vendor SDKs via the `EmbeddingProvider` interface.
- **Order Preservation**: Guarantees that output `EmbeddingResult` sequence strictly matches the original input sequence, even across multiple batches and retried requests.
- **Contract Enforcement**: Validates that provider responses match input counts and format.

### Explicit Non-Responsibilities (Out of Scope)
- ❌ **Vector Store Persistence**: Does not interact with Qdrant, Milvus, Pinecone, or PostgreSQL pgvector.
- ❌ **Vector Search & Retrieval**: Does not execute similarity searches, nearest neighbor lookups, or hybrid BM25/RRF fusion.
- ❌ **Reranking**: Does not cross-encode or rerank retrieved candidate chunks.
- ❌ **LLM Generation**: Does not generate answers or prompt LLMs.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       EmbeddingService                       │
├──────────────────────────────────────────────────────────────┤
│ - provider: EmbeddingProvider                                │
│ - batch_size: int = 20                                       │
│ - max_tokens: int = 8191                                     │
│ - max_retries: int = 3                                       │
│ - retry_base_delay: float = 1.0                              │
│ - token_counter: TokenCounter                                │
├──────────────────────────────────────────────────────────────┤
│ + embed_texts(texts: Sequence[str]) -> list[EmbeddingResult] │
│ + embed_chunks(chunks: Sequence[Chunk]) -> list[EmbeddingResult]│
└────────────────┬─────────────────────────────────────────────┘
                 │ calls
                 ▼
┌─────────────────────────────────┐
│     «interface»                 │
│     EmbeddingProvider           │
├─────────────────────────────────┤
│ + embed_batch(texts: list[str]) │
│   -> list[list[float]]          │
└───────────────▲─────────────────┘
                │
     ┌──────────┴──────────┐
     │                     │
┌────┴───────────────┐ ┌───┴──────────────────────┐
│ FakeEmbeddingProvider│ │ OpenAIEmbeddingProvider │
│ (Deterministic, test)│ │ (Production OpenAI API)│
└────────────────────┘ └──────────────────────────┘
```

---

## Data Models

Located in [`app/embeddings/models.py`](../../rag-service/app/embeddings/models.py). Both models are immutable (`ConfigDict(frozen=True)`).

### `EmbeddingRequest`
Internal representation of an item to be embedded within a batch:
| Field   | Type  | Constraints       | Description                                  |
|---------|-------|-------------------|----------------------------------------------|
| `text`  | `str` | `min_length=1`    | Validated non-empty chunk text               |
| `index` | `int` | `ge=0`            | Original position in the user's input sequence|

### `EmbeddingResult`
Output unit returned by `embed_texts()` and `embed_chunks()`:
| Field         | Type          | Description                                                    |
|---------------|---------------|----------------------------------------------------------------|
| `index`       | `int`         | 0-based position matching the input sequence                   |
| `embedding`   | `list[float]` | Dense floating-point vector from provider                      |
| `token_count` | `int`         | Calculated number of tokens consumed by this text item         |

---

## Token Counting

Located in [`app/embeddings/token_counter.py`](../../rag-service/app/embeddings/token_counter.py).

Token counting ensures that texts do not exceed the embedding model's context window (e.g., 8,191 tokens for `text-embedding-3-small`).

### Implementations

1. **`CharApproxTokenCounter`** (Default / Zero Dependencies):
   - Fast approximation using character count: `math.ceil(len(text) / 4)`.
   - Conservative for English prose, requiring no external packages or tokenizer data.

2. **`TiktokenCounter`** (Exact BPE Tokenization):
   - Uses OpenAI's `tiktoken` library when installed.
   - Falls back gracefully to `CharApproxTokenCounter` if `tiktoken` is not installed.

3. **`make_token_counter(model: str, auto: bool = True)`**:
   - Factory that detects whether `tiktoken` is available and returns the appropriate counter.

---

## Embedding Providers

Located in [`app/embeddings/providers.py`](../../rag-service/app/embeddings/providers.py).

### `EmbeddingProvider` (ABC)
Defines the provider contract:
```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
```

### `FakeEmbeddingProvider`
Deterministic provider designed for unit and integration testing without external services:
- Generates reproducible float vectors of fixed dimension (default: 8).
- Tracks `call_count` and `received_batches` for test assertion.
- Supports fault injection via `fail_on_calls={...}` (transient) and `permanent_fail_on_calls={...}` (permanent).
- Requires zero external dependencies and makes no network calls.

### `OpenAIEmbeddingProvider`
Production provider using the `openai` SDK:
- Supports `text-embedding-3-small`, `text-embedding-3-large`, and `text-embedding-ada-002`.
- Classifies provider exceptions into transient (`RateLimitError`, `APITimeoutError`, `InternalServerError`) vs permanent (`AuthenticationError`, `BadRequestError`).
- Lazily imports `openai` and raises an informative `ImportError` if the package is missing.

---

## Error Handling & Retry Policies

Located in [`app/embeddings/exceptions.py`](../../rag-service/app/embeddings/exceptions.py).

### Exception Hierarchy

```
EmbeddingError
  ├── EmbeddingValidationError      (HTTP 400 equivalent: empty input, bad config)
  ├── EmbeddingTokenLimitError      (HTTP 422 equivalent: text exceeds token ceiling)
  ├── EmbeddingProviderError        (Provider error; flag: is_transient = True/False)
  └── EmbeddingRetryExhaustedError  (Exhausted all retry attempts for transient errors)
```

### Transient vs. Permanent Error Classification

| Error Type | Example Causes | `is_transient` | Behavior |
|------------|----------------|----------------|----------|
| Rate Limit | OpenAI HTTP 429, Quota exceeded | `True` | Retried with exponential backoff + jitter |
| Network Timeout | API timeout, connection reset | `True` | Retried with exponential backoff + jitter |
| Server Error | HTTP 500, 502, 503 | `True` | Retried with exponential backoff + jitter |
| Auth Failure | Invalid API key (HTTP 401) | `False` | Aborts immediately (NO retry) |
| Bad Request | Malformed payload (HTTP 400) | `False` | Aborts immediately (NO retry) |
| Contract Mismatch | Provider returned wrong count or malformed vectors | `False` | Aborts immediately (NO retry) |
| Token Exceeded | Chunk exceeds max_tokens | N/A | Aborts before calling provider |

### Exponential Backoff with Full Jitter

Between retry attempts, the delay is calculated as:
$$\text{delay} = \text{retry\_base\_delay} \times 2^{\text{attempt} - 1} + \text{uniform}(0, 0.5)$$

- Attempt 1 (1st retry): $1.0\text{s} + [0, 0.5]\text{s} \in [1.0\text{s}, 1.5\text{s}]$
- Attempt 2 (2nd retry): $2.0\text{s} + [0, 0.5]\text{s} \in [2.0\text{s}, 2.5\text{s}]$
- Attempt 3 (3rd retry): $4.0\text{s} + [0, 0.5]\text{s} \in [4.0\text{s}, 4.5\text{s}]$

For unit testing, injecting `sleep_fn=lambda _: None` allows instant retries without wall-clock delays.

---

## Configuration Reference

Settings in [`app/core/config.py`](../../rag-service/app/core/config.py) (managed via `pydantic-settings`):

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | `str` | Model identifier |
| `EMBEDDING_BATCH_SIZE` | `20` | `int` | Maximum items per provider batch call |
| `EMBEDDING_MAX_TOKENS` | `8191` | `int` | Maximum tokens permitted per chunk |
| `EMBEDDING_MAX_RETRIES` | `3` | `int` | Maximum transient retry attempts per batch |
| `EMBEDDING_RETRY_BASE_DELAY` | `1.0` | `float` | Base delay for backoff (seconds) |
| `OPENAI_API_KEY` | `""` | `str` | OpenAI API key (optional in dev/test) |

---

## Usage Examples

### Direct Text Embedding
```python
from app.embeddings import EmbeddingService, FakeEmbeddingProvider

provider = FakeEmbeddingProvider(dimension=1536)
service = EmbeddingService(
    provider=provider,
    batch_size=20,
    max_tokens=8191,
    max_retries=3,
)

texts = ["First chunk of document", "Second chunk of document"]
results = service.embed_texts(texts)

for r in results:
    print(f"Index {r.index}: vector dim {len(r.embedding)}, tokens: {r.token_count}")
```

### Document Chunks Embedding
```python
from app.embeddings import create_embedding_service
from app.ingestion.chunking import RecursiveChunker

# Chunker generates list[Chunk]
chunker = RecursiveChunker(target_chunk_size=500, overlap=50)
chunks = chunker.chunk(document)

# Service embeds chunk contents preserving chunk indices
service = create_embedding_service()
results = service.embed_chunks(chunks)
```

---

## Verification & Test Suite

The test suite in [`tests/test_embedding_service.py`](../../rag-service/tests/test_embedding_service.py) contains 40 test cases:
- **Batching**: empty input, smaller than batch size, equal to batch size, multi-batch splitting, ordering, chunk wrapper.
- **Token Limits**: under limit, at exact limit, exceeding limit, pre-call validation (zero provider calls on error).
- **Retry Logic**: transient recovery, multiple transient retries, retries exhausted, permanent errors unretried, delay calculation, custom sleep function.
- **Input Validation**: empty string, whitespace string, non-string type, negative/zero batch size, max tokens, retries, delay.
- **Provider Contract**: wrong count, non-list, empty vector, non-numeric elements.
- **Counters & Factory**: char counter, fallback resolution, service factory.
- **Data Models**: immutability, field constraints.
