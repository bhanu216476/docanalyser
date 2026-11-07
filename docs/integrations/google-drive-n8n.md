# Google Drive + n8n Document Ingestion — Architecture Reference

> **Setup guide**: See [`google-drive-n8n-oauth-setup.md`](./google-drive-n8n-oauth-setup.md)
> for the step-by-step Google OAuth2 configuration instructions.

---

## Architecture Overview

```
Google Drive Folder
    |
    | (new / updated file detected — polling every minute)
    v
n8n Workflow  (google_drive_ingestion_workflow.json)
    |
    | 1. Google Drive Trigger — detect new/updated file
    | 2. Download Drive File — download binary via Google Drive OAuth2
    | 3. Validate Format & Size — check extension (pdf/txt/md), max 15 MB
    | 4. Extract Metadata & Compute SHA-256 — build base64 data URI
    v
POST /api/internal/documents/ingest
X-Internal-Token: <N8N_INGESTION_TOKEN>
Content-Type: application/json
    |
    | {
    |   "documentId": "<deterministic UUID from Drive fileId>",
    |   "fileName":   "report.pdf",
    |   "fileType":   "pdf",
    |   "mimeType":   "application/pdf",
    |   "source":     "google-drive",
    |   "fileSize":   524288,
    |   "contentHash":"sha256:deadbeef...",
    |   "fileData":   "data:application/pdf;base64,JVBERi0..."
    | }
    v
Spring Boot — IngestionController
    |
    | - Authenticates X-Internal-Token via InternalApiKeyFilter
    | - Checks contentHash for duplicate detection
    | - Creates / updates Document entity in PostgreSQL
    | - Decodes base64 fileData → byte[] in RagServiceClient
    v
POST /api/v1/rag/ingest  (multipart/form-data)
    |
    | file: <decoded binary>
    | document_id: <UUID>
    v
Python FastAPI RAG Service
    |
    | - Writes to temp file
    | - Runs ingestion pipeline:
    |     - Text extraction
    |     - Semantic chunking
    |     - Embedding generation
    |     - Qdrant vector insertion
    |     - BM25 indexing
    v
Qdrant Vector Store + BM25 Index
```

---

## Implementation Status

| Component | Status | Notes |
|---|---|---|
| n8n workflow JSON | ✅ Created | `infrastructure/n8n/google_drive_ingestion_workflow.json` |
| Spring Boot `IngestionRequest` | ✅ Updated | Added `fileData`, `fileSize`, `mimeType`, `ownerId` |
| `RagServiceClient` base64 path | ✅ Updated | Decodes `data:mime;base64,...` before multipart upload |
| `IngestionController` update logic | ✅ Updated | Handles DOCUMENT_UPDATED (new hash → re-index) |
| RAG `rag.py` `document_id` param | ✅ Updated | Accepts optional `document_id` form field |
| `rag_pipeline.py` pre-ingest cleanup | ✅ Updated | Deletes old Qdrant vectors + BM25 entries before re-index |
| `application.yml` multipart limits | ✅ Updated | 25 MB max file size + request size |
| Google OAuth2 credentials | ⏳ Pending | Manual step — follow the OAuth2 setup guide |
| End-to-end verification | ⏳ Pending | Requires OAuth credentials and running n8n |

---

## Spring Boot Internal Endpoint

**`POST /api/internal/documents/ingest`**

Protected by `InternalApiKeyFilter`. Validates the `X-Internal-Token` header
against the `app.internal.api-token` / `N8N_INGESTION_TOKEN` environment variable.

### Request Headers

```
Content-Type: application/json
X-Internal-Token: <your N8N_INGESTION_TOKEN>
```

### Request Body (Updated — binary transfer via base64)

```json
{
  "documentId":  "550e8400-e29b-41d4-a716-446655440000",
  "fileName":    "Q3-Report.pdf",
  "fileType":    "pdf",
  "mimeType":    "application/pdf",
  "source":      "google-drive",
  "fileSize":    524288,
  "contentHash": "sha256:deadbeef...",
  "fileData":    "data:application/pdf;base64,JVBERi0xLjUKJYCBgoMK..."
}
```

> **Why base64 instead of a file path?**  
> The original design sent `filePath` assuming n8n and Spring Boot share a
> filesystem. In containerised / cloud deployments they do not. The updated
> design encodes the file binary as a base64 `data:` URI inside `fileData`.
> `RagServiceClient` decodes this before uploading to the FastAPI service via
> `multipart/form-data`. This works correctly in Docker Compose, Render, Fly.io,
> and all other deployment environments.

> **Why not send a Google Drive URL?**  
> Google Drive download URLs require OAuth2 authorisation. Spring Boot does not
> hold a Google OAuth token, so a plain HTTP download would fail. Sending the
> binary from n8n (which already holds the OAuth credential) is the correct approach.

### Response: `202 Accepted`

```json
{
  "documentId": "550e8400-e29b-41d4-a716-446655440000",
  "status":     "PROCESSING"
}
```

### Duplicate document response: `200 OK`

```json
{
  "documentId": "550e8400-e29b-41d4-a716-446655440000",
  "status":     "READY",
  "message":    "Duplicate document ignored"
}
```

### Document update response: `202 Accepted`

When the same `documentId` is re-submitted with a different `contentHash`
(i.e. the file was modified in Google Drive):

```json
{
  "documentId": "550e8400-e29b-41d4-a716-446655440000",
  "status":     "PROCESSING",
  "message":    "Document update queued"
}
```

---

## n8n Workflow — Node Summary

The workflow is in `infrastructure/n8n/google_drive_ingestion_workflow.json`.

| # | Node | Purpose |
|---|---|---|
| 1 | Google Drive Trigger | Polls the target folder every minute for new/updated files |
| 2 | Manual / Test Webhook | Alternative trigger for manual testing |
| 3 | Download Drive File | Downloads binary via Google Drive OAuth2 |
| 4 | Validate Format & Size | Rejects unsupported types and files > 15 MB |
| 5 | Is File Valid? | IF branch — routes valid vs. rejected |
| 6 | Extract Metadata & Compute SHA-256 | Deterministic UUID from Drive fileId; SHA-256 of binary; base64 encoding |
| 7 | Send to Spring Boot Ingestion API | POST with `X-Internal-Token` and `fileData` base64 |
| 8 | Check Ingestion Status | Routes success (2xx) vs. failure |
| 9 | Format Success Report | Structured success output |
| 10 | Format Ingestion Failure | Error output for Spring Boot failures |
| 11 | Format Validation Failure | Error output for rejected files |

---

## Environment Variables

### n8n

| Variable | Description | Required |
|---|---|---|
| `N8N_INGESTION_TOKEN` | Shared secret for `X-Internal-Token` header | ✅ |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID to monitor | ✅ |
| `SPRING_BOOT_URL` | Base URL of Spring Boot backend | ✅ |
| `N8N_ENCRYPTION_KEY` | 32+ char key to encrypt stored credentials — set once, never change | ✅ |
| `N8N_HOST` | Public hostname of n8n (needed for OAuth callback) | Production only |
| `N8N_PROTOCOL` | `https` for production | Production only |

### Spring Boot

| Variable | Description |
|---|---|
| `N8N_INGESTION_TOKEN` / `app.internal.api-token` | Must match n8n's `N8N_INGESTION_TOKEN` |
| `RAG_SERVICE_URL` | FastAPI RAG service base URL |

### RAG Service

| Variable | Description |
|---|---|
| `N8N_INGESTION_TOKEN` | Used as an optional internal auth check |
| `QDRANT_URL` | Qdrant vector store URL |

> **Security**: Generate tokens with `openssl rand -hex 32`.  
> Never use the default `docanalyser-n8n-internal-token-secret` in production.  
> Never commit secrets to version control.

---

## Deduplication and Update Logic

### Same file content (same SHA-256 hash)
- `IngestionController` finds an existing document with matching `contentHash`
- Returns `200 OK` with `"Duplicate document ignored"` — no re-indexing

### Same file, updated content (same `documentId`, different hash)
- `IngestionController` recognises the existing document by `documentId`
- Updates metadata (`contentHash`, `fileSize`, `mimeType`, `fileName`)
- Sets status to `PENDING` and queues re-ingestion
- `rag_pipeline.py` deletes old Qdrant vectors and BM25 entries before re-indexing

### New file (new `documentId`, no hash collision)
- `IngestionController` creates a new `Document` entity
- Full ingestion pipeline runs

---

## Supported File Types

| Format | MIME Type | Supported |
|---|---|---|
| PDF | `application/pdf` | ✅ |
| Plain Text | `text/plain` | ✅ |
| Markdown | `text/markdown` | ✅ |
| DOCX | `application/vnd.openxmlformats-...` | ❌ Not supported by existing pipeline |
| Images | `image/*` | ❌ |

**Maximum file size**: 15 MB (workflow validation) / 25 MB (Spring Boot multipart limit)

---

## Error Handling

The workflow produces structured output for each failure scenario:

| Scenario | Workflow output |
|---|---|
| Unsupported file type | `Format Validation Failure` node — includes file name and reason |
| File > 15 MB | `Format Validation Failure` node |
| Spring Boot returns non-2xx | `Format Ingestion Failure` node — includes status code and response body |
| RAG service failure | Spring Boot returns 5xx → `Format Ingestion Failure` node |

---

## Related Files

| File | Description |
|---|---|
| `docs/integrations/google-drive-n8n-oauth-setup.md` | Step-by-step OAuth2 credential setup |
| `infrastructure/n8n/google_drive_ingestion_workflow.json` | n8n workflow to import |
| `infrastructure/docker-compose.yml` | Local dev environment (includes n8n) |
| `backend/.../dto/request/IngestionRequest.java` | Request DTO (includes `fileData`, `fileSize`, `mimeType`) |
| `backend/.../service/RagServiceClient.java` | Decodes base64 → multipart upload to FastAPI |
| `backend/.../controller/IngestionController.java` | Deduplication + update logic |
| `rag-service/app/api/rag.py` | FastAPI ingest endpoint (`document_id` param) |
| `rag-service/app/pipeline/rag_pipeline.py` | Pre-ingest cleanup for document updates |
