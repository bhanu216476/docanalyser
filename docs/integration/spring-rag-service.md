# Spring to Python RAG integration

Spring exposes `POST /api/v1/documents` for n8n and forwards the request to the Python RAG service at the same path.

## Request

```json
{
  "event": "DOCUMENT_ADDED",
  "document_id": "unique-document-id",
  "file_name": "research.txt",
  "source_url": "C:/documents/research.txt",
  "content_type": "text/plain",
  "metadata": {
    "source": "google_drive",
    "folder_id": "folder-123",
    "modified_time": "2026-09-26T10:00:00Z"
  },
  "version": "2026-09-26T10:00:00Z"
}
```

Supported events are `DOCUMENT_ADDED`, `DOCUMENT_UPDATED`, and `DOCUMENT_DELETED`. `document_id` is required for every event. Add and update events also require `file_name` and `source_url`.

The current Python loader contract accepts a local filesystem path in `source_url`; it does not download Google Drive content. n8n or a preceding service must make the referenced file available to the Python service. The existing PDF, Markdown, and text loaders then perform ingestion, chunking, embedding, Qdrant upsert, and BM25 indexing.

## Semantics

- Added: ingest the source using the supplied `document_id`.
- Updated: delete all Qdrant and BM25 chunks for `document_id`, then ingest the current source.
- Deleted: delete only chunks matching `document_id`.
- Repeated add/update requests are safe because old chunks are removed for updates and chunk point IDs are deterministic.

Successful processing returns `200` with `status: "PROCESSED"`. Validation errors return `400` or `422`; missing local sources return `404`; downstream processing failures return `500`.

## Configuration

Spring uses the required `RAG_SERVICE_URL` environment variable through `rag.service.url`. An optional `rag.service.internal-token` value is sent as a Bearer token. No URL or secret is hard-coded into the n8n workflow.