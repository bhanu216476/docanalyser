# Document Chunking Architecture

Chunking is the process of dividing a loaded `Document` into discrete, overlapping or non-overlapping text segments called `Chunk`s. These chunks become the unit of downstream embedding generation and vector search.

---

## Why Chunking Is Needed

```
Large Document
      │
      ▼
 Smaller Chunks
      │
      ▼
  Embeddings
      │
      ▼
 Vector Store
      │
      ▼
  Retrieval
```

Language models and embedding models operate within a fixed token limit. Passing an entire large document to an embedding model is infeasible and produces a single vector that loses local semantic detail. Chunking solves this by creating focused, semantically meaningful windows that:

1. Fit within embedding model token limits.
2. Give the vector index fine-grained, retrievable units.
3. Allow the RAG retriever to return precise, relevant passages rather than entire documents.

---

## Chunk Model

Every chunk is represented by the canonical `Chunk` Pydantic model defined in [`app/ingestion/chunking/models.py`](../../rag-service/app/ingestion/chunking/models.py).

### Fields

| Field         | Type             | Purpose                                                                 |
|---------------|------------------|-------------------------------------------------------------------------|
| `chunk_id`    | `str`            | Deterministic unique identifier: `{document_id}:{chunk_index}`          |
| `document_id` | `str`            | Identifier of the source document for provenance and citation           |
| `content`     | `str`            | Non-empty text content of the chunk (min_length=1, validated)           |
| `chunk_index` | `int`            | 0-based sequential ordering index within the document                  |
| `start_char`  | `Optional[int]`  | Starting character offset in the source document                        |
| `end_char`    | `Optional[int]`  | Ending character offset in the source document                          |
| `metadata`    | `dict[str, Any]` | Source document metadata + chunking parameters + section hierarchy      |

The model is **frozen** (immutable) via `ConfigDict(frozen=True)`.

### Chunk ID Strategy

```
chunk_id = f"{document_id}:{chunk_index}"
```

**Rationale**: Deterministic IDs ensure the same document chunked with the same configuration always produces identical, predictable chunk IDs across pipeline runs. This enables:
- Idempotent upserts to vector stores.
- Tracing chunks back to their source document.
- Stable references in citation responses.

`document_id` resolution priority (in `BaseChunker._resolve_document_id`):
1. `document.metadata["document_id"]` (set by PostgreSQL persistence layer)
2. `document.metadata["id"]`
3. `document.metadata["content_hash"]`
4. SHA-256 hash computed directly from `document.content`

### Design for Future Extension

The `metadata` dict is the designated extension point. Future embedding fields (`embedding_vector`, `embedding_model`, `embedding_dimension`) can be added to a new `EmbeddedChunk` subclass or a separate storage model **without redesigning the `Chunk` model**.

---

## BaseChunker Interface

```python
from abc import ABC, abstractmethod

class BaseChunker(ABC):
    def chunk(self, document: Document) -> list[Chunk]: ...
    def chunk_documents(self, documents: Sequence[Document]) -> list[Chunk]: ...
```

All chunking strategies inherit from `BaseChunker`, ensuring the rest of the pipeline can swap strategies without change. Both implementations accept identical `Document` inputs and produce identical `Chunk` outputs.

---

## Fixed-Size Chunking

Implemented in [`app/ingestion/chunking/fixed_size.py`](../../rag-service/app/ingestion/chunking/fixed_size.py).

### Algorithm

1. Measure document content length in characters.
2. If content fits within `chunk_size`, return a single chunk.
3. Otherwise apply a sliding window:
   - `Chunk 0`: `content[0 : chunk_size]`
   - `Chunk 1`: `content[step : step + chunk_size]` where `step = chunk_size - overlap`
   - Continue until the end of the document is reached.

```
chunk_size = 10, overlap = 3

Chunk 0:  [0123456789]
Chunk 1:        [6789ABCDEF]
Chunk 2:              [CDEFGHIJKL]
```

### Size Unit: Characters

| Decision | Rationale |
|---|---|
| **Characters** chosen | Standard Python string slicing — zero external dependencies, platform-independent, fully deterministic |
| Not tokens | Token count requires a tokenizer (e.g. `tiktoken`) — premature dependency for this stage |
| Not words | Word-splitting is ambiguous across languages, scripts, and punctuation conventions |

**Limitations of character-based chunking**:
- A 1000-character chunk may contain very different token counts depending on content (dense code vs. prose).
- When embedding models are selected, a **token-aware chunker** should be evaluated to ensure chunks stay within model context windows.

### Configuration & Defaults

| Parameter | Default | Constraint |
|---|---|---|
| `chunk_size` | `1000` | `> 0` |
| `overlap` | `200` | `>= 0` and `< chunk_size` |

Defaults are intentionally modest — 1000 characters gives roughly 200–300 tokens for typical English prose, well within common embedding model limits (e.g. 512–8192 tokens).

### Edge Case Behaviour

| Scenario | Result |
|---|---|
| Empty / whitespace-only document | `[]` (empty list) — no chunks emitted |
| Document `<= chunk_size` characters | 1 chunk containing full content |
| Document `== chunk_size` characters | 1 chunk containing full content |
| Document `> chunk_size` characters | Multiple ordered chunks |
| `overlap = 0` | Non-overlapping contiguous chunks |
| `overlap >= chunk_size` | `ValueError` raised immediately |
| `chunk_size <= 0` | `ValueError` raised immediately |

---

## Recursive / Structure-Aware Chunking

Implemented in [`app/ingestion/chunking/recursive.py`](../../rag-service/app/ingestion/chunking/recursive.py).

### Design Goal

Preserve semantic boundaries rather than cutting at arbitrary character positions. When a section fits within `chunk_size`, it is emitted whole. When it does not, it is subdivided using progressively finer separators.

### Separator Hierarchy

The algorithm tries separators from coarsest to finest:

| Priority | Separator | Rationale |
|---|---|---|
| 1 | Markdown headings (`# – ######`) | Highest semantic unit for structured docs |
| 2 | Paragraph breaks (`\n\n`) | Natural prose section boundaries |
| 3 | Line breaks (`\n`) | Secondary structure within paragraphs |
| 4 | Sentence endings (`.!?` + whitespace) | Semantic unit of meaning |
| 5 | Whitespace (` `) | Word-level granularity |
| 6 | Character (`""`) | Last-resort fallback for unbroken strings |

For non-Markdown documents, heading splitting is skipped and the algorithm starts at paragraph boundaries.

### Markdown Heading Context (Structure Awareness)

For Markdown files, the algorithm:

1. Scans all headings with `re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)`.
2. Maintains a **heading stack** tracking the hierarchy:
   ```
   # Company Policies          → stack: [(1, "Company Policies")]
   ## Leave Policy             → stack: [(1, "Company Policies"), (2, "Leave Policy")]
   ## Remote Work              → stack: [(1, "Company Policies"), (2, "Remote Work")]
   ```
3. Propagates the current breadcrumb into every chunk generated within that section:
   ```python
   chunk.metadata["headings"] = ["Company Policies", "Leave Policy"]
   chunk.metadata["section"]  = "Company Policies > Leave Policy"
   ```

**Design decision**: A lightweight breadcrumb string is chosen over embedding full heading content into every chunk. This is sufficient for:
- LLM citation formatting ("Source: *Company Policies > Leave Policy*").
- Filter-based retrieval (filter by section/heading metadata).
- Human review of retrieval results.

**Empty sections are silently skipped** — a heading with no body text does not emit an empty chunk, but remains in the heading stack to provide context for subsequent child headings.

### Recursive Splitting Algorithm

```
split_text(text, separators):
    if len(text) <= chunk_size:
        return [text]
    find first separator present in text
    split text by separator → segments[]
    for each segment:
        if len(segment) > chunk_size:
            recurse with remaining separators
    merge adjacent segments up to chunk_size with overlap
    return chunks
```

This ensures:
- No arbitrary cuts when a semantic boundary fits.
- Correct recursive subdivision of oversized sections down to character level.
- Overlap is respected during segment merging.

### Configuration & Defaults

| Parameter | Default | Constraint |
|---|---|---|
| `chunk_size` | `1000` | `> 0` |
| `overlap` | `200` | `>= 0` and `< chunk_size` |
| `separators` | See hierarchy above | Custom list supported |

---

## Chunk Metadata Reference

Every chunk's `metadata` dict contains:

| Key | Source | Purpose |
|---|---|---|
| `document_id` | Resolved from document | Source document identifier for citation |
| `source` | `document.source` | Full file path for provenance |
| `file_name` | `document.file_name` | Basename for citation display |
| `file_type` | `document.file_type` | File type for format-aware processing |
| `chunk_index` | Assigned by chunker | Position within the document |
| `chunk_size` | Chunker config | Effective `chunk_size` setting |
| `overlap` | Chunker config | Effective `overlap` setting |
| `strategy` | `"fixed_size"` or `"recursive"` | Which chunker produced this chunk |
| `headings` *(recursive only)* | Parsed from Markdown | Heading breadcrumb list |
| `section` *(recursive only)* | Derived from headings | Human-readable section path |

---

## Module Structure

```
rag-service/app/ingestion/chunking/
├── __init__.py       # Package exports
├── base.py           # BaseChunker abstract class + shared utilities
├── models.py         # Chunk Pydantic model
├── fixed_size.py     # FixedSizeChunker implementation
└── recursive.py      # RecursiveChunker implementation
```

---

## Strategy Comparison

| Aspect | FixedSizeChunker | RecursiveChunker |
|---|---|---|
| **Algorithm** | Sliding window character slices | Hierarchical separator recursion |
| **Boundary awareness** | None — may split mid-sentence | Paragraph, line, sentence, word |
| **Markdown support** | None | Heading hierarchy with breadcrumbs |
| **Metadata** | Source provenance only | Source + section headings + hierarchy |
| **Predictability** | Very high — purely deterministic | High — deterministic but structure-dependent |
| **Complexity** | Low | Medium |
| **Best for** | Uniform documents, bulk ingestion | Markdown, structured documentation |

---

## Future Considerations

The following strategies may be worth evaluating in future phases:

### Token-Aware Chunking
When a specific embedding model is selected, replacing character-count with token-count (`tiktoken` or equivalent) ensures chunks respect model context window limits accurately. This should be implemented as a new `TokenAwareChunker(BaseChunker)` subclass.

### Semantic Chunking
Uses embedding similarity of adjacent sentences to find natural semantic breakpoints. Requires an embedding model at ingestion time — deferred until the embedding layer is introduced.

### Chunk Size & Overlap Experimentation
Retrieval quality is sensitive to `chunk_size` and `overlap`. Recommended future experimentation:
- Compare `chunk_size ∈ {256, 512, 1000, 2000}` against retrieval recall.
- Compare `overlap ∈ {0, 10%, 20%}` of `chunk_size`.
- Automate evaluation with a held-out retrieval benchmark.

### Multi-modal Chunking
For PDF and HTML documents, structure-aware chunking must account for page breaks, tables, headers/footers, and embedded images.
