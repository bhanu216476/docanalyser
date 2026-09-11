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

## Chunking

The RAG Service implements three modular document chunking strategies to compare segmentation behavior ahead of embedding and vector index evaluation:

1. **Fixed-Size Chunking (`fixed`)**: Slices documents using fixed character lengths and configurable overlap (`chunk_size=1000`, `chunk_overlap=100`).
2. **Recursive Character Chunking (`recursive`)**: Uses hierarchical text splitting (paragraphs → lines → words → characters) to respect structural text boundaries.
3. **Semantic Chunking (`semantic`)**: Evaluates semantic similarity across neighboring text units using cosine distance between sentence vector embeddings. Breakpoint thresholds (`percentile`, `standard_deviation`, `interquartile`, `absolute`) determine semantic chunk boundaries.

### Dependency Injection & Deterministic Testing

The semantic chunking module uses **dependency injection** for the embedding model, accepting any object conforming to `langchain_core.embeddings.Embeddings`. Unit tests and offline benchmarks run deterministically using a zero-network `FakeEmbeddings` provider.

### Metadata Preservation & Page Spanning

All chunking strategies preserve original document metadata fields (`source`, `source_type`, `headings`, `page`, `page_number`, custom metadata) and attach normalized chunk tracking attributes:
- `chunk_id`: Unique identifier (`{doc_id}_chunk_{index}`)
- `chunk_index`: 0-based chunk sequence index within the logical parent (`document_id`)
- `chunking_strategy`: Strategy name (`fixed`, `recursive`, `semantic`)
- `total_chunks`: Total chunk count for the logical parent (`document_id`)
- `page_numbers`: List of 1-based page numbers covered by the chunk when spanning multiple pages

### Empirical 100-Page Benchmark

A synthetic 100-page technical research paper benchmark suite (`tests/chunking/test_chunk_comparison.py`) evaluates all three strategies:

`Page Crossings` counts chunks whose `page_numbers` contain more than one distinct page. `Heading Chunks` counts chunks with non-empty preserved `headings` metadata. Each strategy is timed around its chunking call only; imports and fake-model construction are outside the timed region. The displayed timing values are illustrative because they vary by machine.

```powershell
.\.venv\Scripts\python -m pytest tests/chunking/test_chunk_comparison.py -s
```

| Strategy | Chunks | Avg Length | Min | Max | Std Dev | Page Crossings | Heading Chunks | Time (ms) | Emb Calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fixed | 100 | 492.23 | 471 | 555 | 19.3 | 0 | 8 | 0.36 | N/A |
| Recursive | 100 | 492.23 | 471 | 555 | 19.3 | 0 | 8 | 0.82 | N/A |
| Semantic | 200 | 244.62 | 141 | 354 | 47.4 | 0 | 16 | 23.38 | 100 |
