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

### Ingestion Processing

Loaded documents pass through a deterministic preprocessing pipeline before future chunking:

```
PDF / HTML loader
    ↓
Extraction cleanup
    ↓
Metadata normalization
    ↓
Page tracking for PDFs
    ↓
Heading extraction
    ↓
Future chunking
```

- **Extraction Cleanup**: Normalizes line endings to `\n`, trims surrounding whitespace, collapses repeated spaces/tabs on lines, and reduces excessive blank lines while conservatively preserving paragraph breaks, punctuation, Unicode characters, and original content meaning without summarization or word removal.
- **Page Tracking**: Normalizes PDF page indexing into a 1-based `page_number` field in metadata for user-facing citations (`page_number: 1`, `source_type: "pdf"`). HTML documents are tagged with `source_type: "html"` and do not receive artificial page numbers.
- **Heading Extraction**: Extracts structured heading titles (`headings: [...]` in metadata) from HTML heading tags (`<h1>`-`<h6>`) or conservative text heuristics for PDF/plain text (Markdown headers, section numbers, title-cased short lines).
