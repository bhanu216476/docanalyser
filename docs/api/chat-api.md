# Chat API

## Base URL

`/api/chat`

All endpoints require a valid JWT Bearer token.

---

## Sessions

### Create Session

**`POST /api/chat/sessions`**

Creates a new chat session for the authenticated user.

**Request body:**
```json
{
  "title": "Contract Analysis Q&A"
}
```

**Response:** `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "title": "Contract Analysis Q&A",
  "createdAt": "2026-09-25T10:00:00Z",
  "updatedAt": "2026-09-25T10:00:00Z"
}
```

---

### List Sessions

**`GET /api/chat/sessions`**

Returns all sessions for the authenticated user, ordered by `createdAt` descending.

**Response:** `200 OK`
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "userId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "title": "Contract Analysis Q&A",
    "createdAt": "2026-09-25T10:00:00Z",
    "updatedAt": "2026-09-25T10:05:30Z"
  }
]
```

---

### Get Session

**`GET /api/chat/sessions/{sessionId}`**

Returns a session and its full message history.

**Auth:** Session must be owned by the caller.

**Path parameters:**

| Name | Type | Description |
|------|------|-------------|
| `sessionId` | UUID | Chat session ID |

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "title": "Contract Analysis Q&A",
  "createdAt": "2026-09-25T10:00:00Z",
  "updatedAt": "2026-09-25T10:05:30Z",
  "messages": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "sessionId": "550e8400-e29b-41d4-a716-446655440000",
      "role": "USER",
      "content": "What are the payment terms?",
      "createdAt": "2026-09-25T10:01:00Z"
    },
    {
      "id": "8f14e0dc-df62-4c7e-b6a4-56e1f67b8b89",
      "sessionId": "550e8400-e29b-41d4-a716-446655440000",
      "role": "ASSISTANT",
      "content": "According to Section 4.2, payment is due within 30 days...",
      "createdAt": "2026-09-25T10:01:02Z"
    }
  ]
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `403` | Session belongs to a different user |
| `404` | Session not found |

---

## Messages

### Send Message

**`POST /api/chat/sessions/{sessionId}/messages`**

Sends a user message and returns the assistant's response from the RAG pipeline.

**Path parameters:**

| Name | Type | Description |
|------|------|-------------|
| `sessionId` | UUID | Chat session ID |

**Request body:**
```json
{
  "content": "What are the payment terms?"
}
```

**Response:** `200 OK` — The assistant's `ChatMessage`

```json
{
  "id": "8f14e0dc-df62-4c7e-b6a4-56e1f67b8b89",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "role": "ASSISTANT",
  "content": "According to the retrieved documents, payment is due within 30 days of invoice.",
  "createdAt": "2026-09-25T10:01:02Z"
}
```

**RAG pipeline unavailable:** If the Python RAG service is unreachable, the assistant returns a graceful error message instead of a 5xx:

```json
{
  "role": "ASSISTANT",
  "content": "I'm sorry, I'm unable to process your request at the moment. Please try again later."
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `403` | Session belongs to a different user |
| `404` | Session not found |
| `400` | Empty message content |

---

## ChatRole Enum

| Value | Description |
|-------|-------------|
| `USER` | Message sent by the human user |
| `ASSISTANT` | Response from the RAG pipeline |

---

## Internal Flow: Spring Boot → Python RAG

When a message is sent:

1. Spring Boot saves the `USER` message to `chat_messages`
2. Calls `RagServiceClient.queryRagService(content)` → `POST http://<rag-service>/api/v1/rag/query`
3. Python RAG pipeline performs: dense retrieval → BM25 → RRF → reranking → context building → LLM generation → citation mapping → confidence scoring
4. Response `answer` field is extracted from the JSON response
5. Spring Boot saves the `ASSISTANT` message to `chat_messages`
6. Returns the assistant message to the client

**RAG Service configuration:**

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `RAG_SERVICE_URL` | `http://localhost:8000` | Python RAG service base URL |
| `RAG_SERVICE_TIMEOUT_SECONDS` | `30` | Request timeout |
