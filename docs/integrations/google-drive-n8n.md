# Google Drive + n8n Document Ingestion

## Overview

```
Google Drive
    |
    | (file created/modified trigger)
    v
n8n Workflow
    |
    | (download file, extract metadata)
    v
POST /api/internal/documents/ingest
X-Internal-Token: <N8N_INGESTION_TOKEN>
    |
    v
Spring Boot (IngestionController)
    |
    | (save Document record, call RAG service)
    v
Python RAG Service
POST /api/v1/rag/ingest
    |
    | (chunk + embed + store)
    v
Qdrant Vector Store
```

---

## Status: NOT VERIFIED (Google Drive credentials unavailable)

> The workflow design is complete and the Spring Boot endpoint is implemented and tested.  
> End-to-end verification requires Google Drive OAuth credentials in n8n, which were not available during Day 19 development.

---

## Spring Boot Internal Endpoint

**`POST /api/internal/documents/ingest`**

Protected by `InternalApiKeyFilter` (not JWT). Validates the `X-Internal-Token` header against the `INTERNAL_API_TOKEN` environment variable.

**Request headers:**
```
Content-Type: application/json
X-Internal-Token: <your N8N_INGESTION_TOKEN>
```

**Request body:**
```json
{
  "fileName": "Q3-Report.pdf",
  "filePath": "/tmp/n8n-downloads/Q3-Report.pdf",
  "fileType": "pdf",
  "mimeType": "application/pdf",
  "source": "google-drive",
  "fileSize": 524288,
  "contentHash": "sha256:deadbeef..."
}
```

**Response:** `202 Accepted`
```json
{
  "documentId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING"
}
```

---

## n8n Workflow Design

### Trigger: Google Drive — Watch Files

- **Event:** File created or updated in target folder
- **Credentials:** Google Drive OAuth2 (configured in n8n credentials)
- **Folder:** Configure the specific Google Drive folder ID to watch

### Node 1: Download File

- Use the **Google Drive — Download** node
- Output: binary file data + metadata (name, size, MIME type, etc.)

### Node 2: Save File to Disk (optional)

If the RAG service needs a local file path:
- Use the **Write Binary File** node
- Save to `/tmp/n8n-downloads/{{ $node["Google Drive Trigger"].json.name }}`

### Node 3: Compute Content Hash (optional but recommended)

Use the **Function** node:
```javascript
const crypto = require('crypto');
const fileContent = $binary.data.data; // base64
const buffer = Buffer.from(fileContent, 'base64');
const hash = 'sha256:' + crypto.createHash('sha256').update(buffer).digest('hex');

return [{ json: { contentHash: hash } }];
```

### Node 4: HTTP Request to Spring Boot

- **Method:** POST
- **URL:** `{{ $env.SPRING_BOOT_URL }}/api/internal/documents/ingest`
- **Headers:**
  ```
  Content-Type: application/json
  X-Internal-Token: {{ $env.N8N_INGESTION_TOKEN }}
  ```
- **Body (JSON):**
  ```json
  {
    "fileName": "{{ $node['Google Drive Trigger'].json.name }}",
    "filePath": "/tmp/n8n-downloads/{{ $node['Google Drive Trigger'].json.name }}",
    "fileType": "{{ $node['Google Drive Trigger'].json.mimeType.split('/')[1] }}",
    "mimeType": "{{ $node['Google Drive Trigger'].json.mimeType }}",
    "source": "google-drive",
    "fileSize": {{ $node['Google Drive Trigger'].json.size }},
    "contentHash": "{{ $node['Compute Hash'].json.contentHash }}"
  }
  ```

---

## Environment Variables

| Variable | Where Set | Description |
|----------|-----------|-------------|
| `INTERNAL_API_TOKEN` | Spring Boot `.env` / secrets | Token validated by `InternalApiKeyFilter` |
| `N8N_INGESTION_TOKEN` | n8n Credentials / Environment | Must match `INTERNAL_API_TOKEN` |
| `SPRING_BOOT_URL` | n8n Environment | URL of Spring Boot service (e.g. `http://spring-boot:8080`) |

> **Security:** `N8N_INGESTION_TOKEN` and `INTERNAL_API_TOKEN` must be the same value and must **never** be committed to version control.  
> Generate a strong random token: `openssl rand -hex 32`

---

## Error Handling

If the Spring Boot endpoint returns a non-2xx response, configure n8n to:

1. Log the error response body
2. Send an alert (email / Slack node)
3. Move the failed file to a quarantine folder in Google Drive

---

## Deduplication

The `IngestionController` checks `contentHash` against existing documents before calling the RAG service.  
If a document with the same hash already exists and its status is `READY`, the endpoint returns:

```json
{
  "documentId": "<existing-id>",
  "status": "READY",
  "message": "Document already indexed"
}
```

This prevents re-indexing identical file content.
