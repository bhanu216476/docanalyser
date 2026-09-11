# Qdrant Vector Storage Architecture

The Qdrant Vector Store layer provides persistence, indexing, schema enforcement, and metadata filtering for dense vector embeddings generated from chunked documents.

---

## 1. Pipeline Position

```
Document (Loader)
      │
      ▼
Chunks (Chunking Pipeline)
      │
      ▼
EmbeddingService (Dense Vector Generation)
      │
      ▼
EmbeddingResult[] + Chunk[]
      │
      ▼
QdrantVectorStore  ◄── [This Component]
      │
      ▼
Qdrant Client
      │
      ▼
Qdrant Collection (Index + Storage)
```

The Qdrant storage module receives generated embeddings alongside their source `Chunk` objects, ensures collection configuration compatibility, assigns deterministic point IDs, validates vector geometry and types, constructs structured payloads, and executes batched upserts into Qdrant collections.

---

## 2. Architectural Boundaries & Non-Goals

### Included Scope (Day 7)
- **Collection Creation & Idempotency**: Safe verification and initialization of Qdrant collections with configured vector dimension and distance metric.
- **Collection Compatibility Validation**: Strict validation of existing collections to detect and reject dimension or distance metric mismatches.
- **Payload Indexing**: Automatic creation of payload indexes on filterable fields (`document_id`, `file_type`, `source`).
- **Deterministic Point ID Generation**: RFC 4122 UUIDv5 generation from chunk IDs to guarantee idempotent upserts.
- **Vector Validation**: Upfront validation of vector dimensions, numeric types, finiteness (rejection of NaN/Inf), and 1-to-1 chunk-embedding alignment.
- **Payload Traceability**: Structured storage of document provenance, chunk metadata, and chunk text in point payloads.
- **Batched Insertion & Retries**: Batching vectors for network efficiency, with bounded exponential backoff on transient connection errors.
- **Controlled Metadata Filtering**: Native Qdrant filter translation with strict field whitelisting.
- **Document-Level Deletion**: Point deletion by `document_id` for safe document re-ingestion workflows.

### Explicit Non-Goals (Out of Scope)
> [!IMPORTANT]
> **Vector similarity search / retrieval is NOT implemented in this stage.**
> The following capabilities are explicitly deferred to subsequent stages:
> - ❌ Vector similarity search (`similarity_search()`, `search()`)
> - ❌ Dense, sparse, or hybrid retrieval
> - ❌ BM25 lexical search
> - ❌ Reciprocal Rank Fusion (RRF)
> - ❌ Cross-encoder reranking
> - ❌ LLM integration and answer generation
> - ❌ User-facing query APIs

---

## 3. Collection Specifications

| Parameter | Default Value | Environment Variable | Rationale |
| :--- | :--- | :--- | :--- |
| **Collection Name** | `documents` | `QDRANT_COLLECTION_NAME` | Project-wide document vector collection name. |
| **Vector Dimension** | `1536` | `QDRANT_VECTOR_SIZE` | Matches output dimension of `text-embedding-3-small`. |
| **Distance Metric** | `Cosine` | `QDRANT_DISTANCE` | Standard for normalized embedding vectors (`Distance.COSINE`). |
| **Local Endpoint** | `http://localhost:6333` | `QDRANT_URL` | Local Qdrant HTTP REST API defined in Docker Compose. |
| **gRPC Port** | `6334` | — | High-performance gRPC endpoint for Qdrant client. |
| **Batch Size** | `64` | `QDRANT_BATCH_SIZE` | Optimal batch size balancing payload size and network round-trips. |
| **Max Retries** | `3` | `QDRANT_MAX_RETRIES` | Bounded retries for transient socket/connection errors. |
| **Base Delay** | `0.5s` | `QDRANT_RETRY_BASE_DELAY` | Base backoff delay with exponential scaling and jitter. |

### Creation & Validation Strategy
1. **Check Existence**: `client.collection_exists(name)` is queried before any operation.
2. **If Absent**: Created with `VectorParams(size=vector_size, distance=distance)`. Immediately creates payload indexes for `document_id`, `file_type`, and `source`.
3. **If Present**: Inspects `client.get_collection(name)` to verify `vectors.size == target_size` and `vectors.distance == target_distance`.
4. **Mismatch Behavior**: Raises `CollectionConfigError` with clear diagnostic information and instructions for manual migration or recreation. Never deletes or overwrites existing collections silently.

---

## 4. Point Structure

Each point stored in Qdrant follows this structure:

```text
PointStruct:
  ├── id:      "d3b07384-d113-5b8c-b010-09c07ec7f212"  (UUIDv5 string)
  ├── vector:  [0.0123, -0.0456, 0.0891, ..., 0.0345]   (1536 floats)
  └── payload: { ... }                                  (VectorPayload schema)
```

### Deterministic Point ID Generation
Qdrant requires point IDs to be unsigned 64-bit integers or RFC 4122 UUID strings. To preserve deterministic chunk IDs (e.g. `doc-123:0`) while satisfying Qdrant's schema:
- If `chunk_id` is already a valid UUID string, it is used directly.
- Otherwise, a deterministic UUIDv5 is generated using `uuid.uuid5(DOCANALYSER_NAMESPACE, chunk_id)` where `DOCANALYSER_NAMESPACE` is `a7e1f480-1a74-4bc3-95c5-67be0bf1e5b2`.
- This ensures that re-ingesting the identical chunk produces the exact same UUID point ID, preventing vector duplication.

---

## 5. Payload Schema

The point payload stores comprehensive provenance and chunk context:

```json
{
  "document_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
  "chunk_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a:0",
  "chunk_index": 0,
  "file_name": "employee_handbook.md",
  "file_type": "md",
  "source": "documents/employee_handbook.md",
  "content": "Employees are entitled to 20 days of paid annual leave...",
  "start_char": 0,
  "end_char": 248,
  "section": "Leave Policy",
  "headings": ["HR Policies", "Leave Policy"],
  "metadata": {}
}
```

### Field Definitions & Types

| Field Name | Type | Indexed | Description |
| :--- | :--- | :--- | :--- |
| `document_id` | `str` (Keyword) | **Yes** | Parent document UUID or identifier. Used for document-level deletion and filtering. |
| `chunk_id` | `str` (Keyword) | No | Original deterministic chunk ID (e.g. `{document_id}:{chunk_index}`). |
| `chunk_index` | `int` (Integer) | No | 0-based sequential position of chunk in the parent document. |
| `file_name` | `str` (Keyword) | No | Basename of originating file (e.g. `handbook.md`). |
| `file_type` | `str` (Keyword) | **Yes** | Lowercase file extension (e.g. `md`, `txt`). |
| `source` | `str` (Keyword) | **Yes** | Normalized source path or URI. |
| `content` | `str` (Text) | No | Text content of the chunk. Stored directly to eliminate secondary DB lookups during retrieval. |
| `start_char` | `int` (Optional) | No | Starting character offset in source document. |
| `end_char` | `int` (Optional) | No | Ending character offset in source document. |
| `section` | `str` (Optional) | No | Section heading or Markdown heading text. |
| `headings` | `list[str]` (Optional) | No | Hierarchical heading path for structured documents. |
| `metadata` | `dict` (Optional) | No | Custom un-indexed metadata attributes. |

### Chunk Content Storage Decision
- **Stored in Payload**: `chunk.content` is intentionally preserved in the vector payload.
- **Rationale**: Retrieval pipelines in RAG need the chunk text to construct context prompts for LLMs. Storing the text in Qdrant avoids round-trip joins against PostgreSQL or object storage during query time.
- **Boundary**: Only individual chunk content is stored. Full raw documents are strictly excluded to avoid bloating memory and vector storage caches.

---

## 6. Metadata Filters

Metadata filtering is implemented using a validated builder pattern over Qdrant native `models.Filter`:

### Whitelisted Filter Fields
To prevent accidental injection of un-indexed fields and preserve query performance, only approved fields may be filtered:
`ALLOWED_FILTER_FIELDS = {"document_id", "file_type", "source", "chunk_index", "file_name", "section"}`

Attempting to filter on unknown fields raises `FilterValidationError`.

### Supported Filter Operations
1. **Filter by Document ID**:
   ```python
   f = VectorStoreFilter(document_id="doc-123")
   ```
2. **Filter by Multiple Document IDs**:
   ```python
   f = VectorStoreFilter(document_id=["doc-1", "doc-2"])
   ```
3. **Filter by File Type**:
   ```python
   f = VectorStoreFilter(file_type="md")
   ```
4. **Filter by Source**:
   ```python
   f = VectorStoreFilter(source="s3://bucket/handbook.md")
   ```
5. **Combined Filters (AND)**:
   ```python
   f = VectorStoreFilter(document_id="doc-123", file_type="md")
   ```
6. **Compound OR Filters**:
   ```python
   f = FilterBuilder.build_or([f1, f2])
   ```

---

## 7. Idempotency & Upsert Semantics

- Every vector point is upserted via `client.upsert()`.
- Because the point ID is deterministically derived from `chunk.chunk_id`, re-processing a document with identical chunks will update existing points in-place rather than creating duplicates.
- Safe re-ingestion workflows can also invoke `store.delete_by_document_id(document_id)` prior to re-indexing to ensure stale chunks from shortened documents are pruned.

---

## 8. Error Handling & Retry Policies

The vector store layer provides a clean domain exception hierarchy:

- `VectorStoreError`: Base domain exception.
- `VectorStoreConnectionError`: Transient connection, timeout, or network reset errors. Eligible for bounded retry.
- `CollectionConfigError`: Permanent vector dimension or distance metric incompatibility. Never retried.
- `VectorValidationError`: Invalid vector geometry, count mismatch, non-numeric elements, or empty vectors. Never retried.
- `FilterValidationError`: Attempt to filter by an unknown or disallowed field. Never retried.
- `VectorStoreBatchError`: Unrecoverable errors returned by Qdrant (e.g. 400 Bad Request). Never retried.

### Retry Strategy
- Transient errors (connection refused, timeouts, HTTP 502/503/504) are retried up to `qdrant_max_retries` (default: 3) with exponential backoff:
  $$\text{delay} = \text{base\_delay} \times 2^{\text{attempt}} + \text{jitter}$$
- Jitter is randomly distributed between 0 and 0.1 seconds to prevent thundering herds.
- Permanent errors fail fast immediately without retry.
