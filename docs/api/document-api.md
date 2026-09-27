# Document API

## Base URL

`/api/documents`

All endpoints require a valid JWT Bearer token.

---

## List Documents

**`GET /api/documents`**

Returns documents visible to the authenticated user.

- **USER role:** returns only documents owned by the calling user
- **ADMIN role:** returns all documents in the system

**Auth:** Bearer token required

**Response:** `200 OK`
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "fileName": "contract.pdf",
    "fileType": "pdf",
    "mimeType": "application/pdf",
    "source": "google-drive",
    "fileSize": 204800,
    "contentHash": "sha256:abc123...",
    "status": "READY",
    "ownerId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "createdAt": "2026-09-25T10:00:00Z",
    "updatedAt": "2026-09-25T10:01:30Z"
  }
]
```

---

## Get Document by ID

**`GET /api/documents/{id}`**

Retrieves a single document.

- **USER role:** only accessible if they own the document
- **ADMIN role:** accessible for any document

**Path parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | UUID | Document ID |

**Response:** `200 OK` — Document object (same schema as above)

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404` | Document not found or not owned by caller |
| `401` | Missing or invalid token |

---

## Delete Document

**`DELETE /api/documents/{id}`**

Deletes a document record. Does **not** remove the physical file from Qdrant or Google Drive.

- **USER role:** only their own documents
- **ADMIN role:** any document

**Path parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | UUID | Document ID |

**Response:** `204 No Content`

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404` | Document not found or not owned by caller |
| `401` | Missing or invalid token |

---

## Document Status Values

| Status | Meaning |
|--------|---------|
| `PENDING` | Uploaded, awaiting processing |
| `UPLOADED` | File received, pre-processing |
| `PROCESSING` | Chunking / embedding in progress |
| `READY` | Successfully indexed in Qdrant |
| `PROCESSED` | Legacy equivalent of READY |
| `FAILED` | Ingestion failed |

---

## Ingest Document (Internal)

**`POST /api/internal/documents/ingest`**

**Not for client use.** Called by the n8n automation workflow only.

**Auth:** `X-Internal-Token: <N8N_INGESTION_TOKEN>` header (not JWT)

**Request body:**
```json
{
  "fileName": "contract.pdf",
  "filePath": "/tmp/downloads/contract.pdf",
  "fileType": "pdf",
  "mimeType": "application/pdf",
  "source": "google-drive",
  "fileSize": 204800,
  "contentHash": "sha256:abc123..."
}
```

**Response:** `202 Accepted`
```json
{
  "documentId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING"
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `401` | Missing or invalid internal token |
| `400` | Invalid request body |
| `503` | Python RAG service unavailable |
