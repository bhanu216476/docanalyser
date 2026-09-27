# Day 22 — Redis Integration with Spring Boot

## Architecture Overview

```text
                     ┌───────────────────────────────────┐
                     │          React Frontend           │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │            Spring Boot            │
                     │  ┌─────────────────────────────┐  │
                     │  │      DocumentService        │  │
                     │  │  (Status, Retry, Caching)   │  │
                     │  └──────┬───────────────┬──────┘  │
                     │         │               │         │
                     └─────────┼───────────────┼─────────┘
                               │               │
            Fast Cache / State │               │ Source of Truth
                               ▼               ▼
                     ┌───────────────────┐   ┌───────────────────┐
                     │   Redis (7.x)     │   │    PostgreSQL     │
                     │                   │   │                   │
                     │ • Doc Cache       │   │ • Documents       │
                     │ • Job Status      │   │ • Users & RBAC    │
                     │ • Session State   │   │ • Chat Sessions   │
                     └───────────────────┘   └───────────────────┘
```

---

## 1. Key Naming Conventions

All Redis keys use a structured, predictable naming scheme defined in `RedisKeys.java`:

| Purpose | Pattern | Example | TTL (Configurable) |
|---------|---------|---------|---------------------|
| Document Job Status | `document:status:{documentId}` | `document:status:cd9c069f-e85d-...` | 24 hours (`86400s`) |
| Document Metadata Cache | `cache:document:{documentId}` | `cache:document:cd9c069f-e85d-...` | 5 minutes (`300s`) |
| Temporary Session State | `session:{sessionId}` | `session:7f8a9b1c-...` | 30 minutes (`1800s`) |

---

## 2. Serialization Strategy

Standard Java native serialization (`JdkSerializationRedisSerializer`) is avoided due to security vulnerabilities and lack of cross-language readability.

We configured JSON-compatible serialization in `RedisConfig.java`:
- **Keys & Hash Keys:** `StringRedisSerializer` (plain UTF-8 text strings).
- **Values & Hash Values:** `GenericJackson2JsonRedisSerializer` powered by an `ObjectMapper` customized with:
  - `JavaTimeModule` for native ISO-8601 formatting of `java.time.Instant`.
  - `SerializationFeature.WRITE_DATES_AS_TIMESTAMPS` disabled.
  - Polymorphic typing enabled (`LaissezFaireSubTypeValidator`, `NON_FINAL`, `@class` property).
  - Sensitive fields (e.g. `User.passwordHash`) explicitly annotated with `@JsonIgnore`.

---

## 3. Document Processing State Machine

The document ingestion lifecycle follows a strict state transition model:

```text
       null
         │
         ▼
     UPLOADED
         │
         ▼
    PROCESSING
      │      │
      │      ▼
      │    FAILED
      │      │ (retry)
      │      ▼
      │   PROCESSING
      │      │
      ▼      ▼
      INDEXED
```

### Transition Matrix

| Current Status | Target Status | Allowed? | Rationale |
|----------------|---------------|----------|-----------|
| `null` | `UPLOADED` | ✅ Yes | Initial document upload / registration |
| `null` | `PENDING` | ✅ Yes | Backward compatibility |
| `UPLOADED` | `PROCESSING` | ✅ Yes | Worker starts chunking, embedding, indexing |
| `PROCESSING` | `INDEXED` | ✅ Yes | Ingestion successfully verified in vector store |
| `PROCESSING` | `FAILED` | ✅ Yes | Ingestion/embedding error occurred |
| `FAILED` | `PROCESSING` | ✅ Yes | Explicit retry operation |
| `INDEXED` | `*` (any) | ❌ No | Terminal state — cannot transition backwards |
| `UPLOADED` | `INDEXED` | ❌ No | Must pass through `PROCESSING` |
| `FAILED` | `INDEXED` | ❌ No | Must be retried through `PROCESSING` |

Transition validation is enforced by `DocumentStateMachine.validateTransition(from, to)`.

---

## 4. PostgreSQL vs Redis State

- **PostgreSQL** is the sole persistent **source of truth** for:
  - User accounts and roles.
  - Documents and ownership metadata.
  - Permanent document status.
  - Chat history and messages.
- **Redis** is used exclusively for:
  - Low-latency cache reads (`cache:document:{id}`).
  - Temporary processing job state (`document:status:{id}`).
  - Ephemeral user session state (`session:{id}`).

### Graceful Fallback (`cache failure != application failure`)
If Redis is down or unreachable:
1. `DocumentCacheService` catches the exception, logs a warning, and falls back to PostgreSQL seamlessly.
2. `DocumentJobStatusService` catches the exception and falls back to the persistent PostgreSQL document record.
3. API endpoints return normal responses with zero customer-facing errors.

---

## 5. Concurrency & Race Condition Safeguard

In asynchronous or distributed ingestion:
- If **Worker A** finishes indexing and marks a document `INDEXED`, but a slow **Worker B** afterwards attempts to report `FAILED` or `PROCESSING`:
  `DocumentJobStatusService.setStatus` checks the existing Redis and database state. If the document is already in `INDEXED` (or legacy `READY`/`PROCESSED`), the race update is ignored and the valid `INDEXED` status is preserved.

---

## 6. Document APIs Extension

### `GET /api/documents/{id}/status`
Retrieves the current job processing status. Checks Redis first, falls back to PostgreSQL.
- Requires authentication (User must own document, or be `ADMIN`).
- Response (when `PROCESSING`):
  ```json
  {
    "jobId": "8f8b8e01-...",
    "documentId": "cd9c069f-...",
    "status": "PROCESSING",
    "startedAt": "2026-09-26T14:15:00Z",
    "updatedAt": "2026-09-26T14:15:30Z"
  }
  ```
- Response (when `FAILED`):
  ```json
  {
    "jobId": "8f8b8e01-...",
    "documentId": "cd9c069f-...",
    "status": "FAILED",
    "startedAt": "2026-09-26T14:15:00Z",
    "updatedAt": "2026-09-26T14:16:00Z",
    "error": "Embedding service timeout"
  }
  ```

### `POST /api/documents/{id}/retry`
Triggers an ingestion retry for a document currently in `FAILED` status:
- Requires authentication (User must own document, or be `ADMIN`).
- Validates that document status is currently `FAILED`. If not (e.g. `INDEXED`), returns `400 Bad Request`.
- Transitions document to `PROCESSING` in PostgreSQL and Redis.
- Evicts any stale document cache.
- Invokes Python RAG ingestion.
- On success: transitions to `INDEXED` in PostgreSQL and Redis.
- On failure: transitions back to `FAILED` with the updated error message.
- Returns `200 OK` with the final `DocumentJobStatus`.

---

## 7. Cache Invalidation Strategy

The Document entity cache (`cache:document:{id}`) is evicted whenever:
1. Document metadata is updated.
2. Document is deleted (`DELETE /api/documents/{id}`).
3. Document processing status transitions (`UPLOADED -> PROCESSING -> INDEXED / FAILED`).
4. An ingestion retry is triggered.

---

## 8. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | *(empty)* | Redis authentication password |
| `CACHE_DOCUMENT_TTL_SECONDS` | `300` | Document entity cache TTL (5 minutes) |
| `SESSION_STATE_TTL_SECONDS` | `1800` | Ephemeral chat session TTL (30 minutes) |
| `JOB_STATUS_TTL_SECONDS` | `86400` | Ingestion job status TTL (24 hours) |

---

## 9. Verification & Test Coverage

- **Spring Boot Suite:** 100 tests (100 passed, 0 failures, 0 errors).
  - `DocumentStateMachineTest`: All valid and forbidden transitions verified.
  - `DocumentJobStatusServiceTest`: Redis storage, PostgreSQL fallback, race condition safeguard verified.
  - `DocumentCacheServiceTest`: Cache hit, miss, TTL, and Redis failure fallback verified.
  - `SessionStateServiceTest`: Ephemeral session touch, read, eviction, and TTL refresh verified.
  - `DocumentControllerTest`: `/status` and `/retry` endpoints verified with owner & admin RBAC.
  - `IngestionControllerTest`: Full state machine lifecycle (`UPLOADED -> PROCESSING -> INDEXED / FAILED`) verified.
- **Python RAG Suite:** 825 passed, 0 failures.
