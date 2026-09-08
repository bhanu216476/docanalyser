# RAG Service

FastAPI service for the hybrid RAG application.

## Run locally

```powershell
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Health check: `GET /api/health`

For local web loading, the service uses `USER_AGENT=IntelliResearch-RAG/0.1`
by default. To override it in PowerShell, set the variable before starting the
service:

```powershell
$env:USER_AGENT = "YourProjectName/1.0"
uvicorn app.main:app --reload
```

## Ingestion

Ingestion currently supports PDF and HTML sources. PDFs are loaded with
`PyPDFLoader` and HTML pages with `WebBaseLoader`; both produce LangChain
`Document` objects while preserving loader metadata for future citations.
Chunking and embeddings are intentionally not part of this stage.
