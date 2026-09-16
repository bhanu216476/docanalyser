# Context Builder Architecture & Specification

## 1. Purpose

The **Context Builder** is the RAG pipeline component responsible for translating ranked candidate retrieval chunks (whether produced by dense retrieval, lexical BM25 search, Reciprocal Rank Fusion, or candidate rerankers) into a clean, structured, token-bounded, and citation-linked evidence block ready for prompt injection into an LLM.

Without a dedicated Context Builder, raw retrieval results often:
- Exceed LLM context limits or consume unnecessarily large token budgets.
- Contain duplicate chunks from hybrid retrieval pathways or multi-stage pipelines.
- Discard source metadata, preventing verifiable source citations.
- Introduce arbitrary or alphabetical ordering, disrupting relevance-ranked evidence presentation.

---

## 2. Responsibilities

The Context Builder fulfills six primary responsibilities:

1. **Deterministic Chunk Selection**: Evaluates candidates in ranking order and selects those that fit within the budget.
2. **Duplicate Removal**: Eliminates duplicate candidate evidence by `chunk_id` (primary key) and exact normalized text (secondary key).
3. **Token Budget Enforcement**: Strictly respects a configurable token budget, including all formatting, citation tags, metadata labels, and section separators.
4. **Metadata Preservation**: Retains document IDs, file names, page numbers, and section headings without hallucinating or fabricating missing attributes.
5. **Evidence Ordering**: Preserves the final reranked/retrieval ranking order deterministically.
6. **Citation ID Assignment**: Generates sequential, deterministic citation tags (`[1]`, `[2]`, `...`) only for selected chunks.

---

## 3. Position in RAG Pipeline

```text
Query
  ↓
Dense Retrieval + BM25 Lexical Retrieval
  ↓
Reciprocal Rank Fusion (RRF)
  ↓
Candidate Reranking (e.g., Cross-Encoder / Model Reranker)
  ↓
Ranked Chunks: Sequence[RetrievalResult | RerankedResult]
  ↓
Context Builder
  ├── 1. Validate & filter invalid items (blank IDs, empty content)
  ├── 2. Deduplicate (chunk_id primary, normalized content secondary)
  ├── 3. Enforce token budget (accounting for formatting overhead)
  ├── 4. Preserve metadata & scores
  ├── 5. Order evidence (preserving final ranking order)
  └── 6. Assign citation IDs ([1], [2], ...)
  ↓
BuiltContext (LLM-ready context text + structured selected chunks & citations)
```

---

## 4. Token Budget & Overhead Accounting

### 4.1 Tokenizer Abstraction
Token counting uses the runtime-checkable protocol `TokenCounter`:

```python
@runtime_checkable
class TokenCounter(Protocol):
    def count(self, text: str) -> int:
        ...
```

Implementations:
- `TiktokenCounter`: Production BPE tokenizer using OpenAI's `tiktoken` library when installed, with a unicode regex fallback when offline.
- `WhitespaceTokenCounter`: Fast, deterministic whitespace/word counter for testing and lightweight environments.
- `DeterministicCharRatioTokenCounter`: Deterministic character-ratio counter for fine-grained budget boundary testing.

### 4.2 Formatting Overhead Accounting
The token budget is **never** evaluated on raw chunk content alone. The Context Builder evaluates the token footprint of the **entire formatted block**:

```text
[1]
source: leave_policy.pdf
page: 4

Employees receive 12 casual leave days.
```

The `BudgetTracker` dynamically accounts for:
- Bracketed citation identifier (`[1]`)
- Metadata lines (`source: ...`, `page: ...`, `section: ...`)
- Inter-chunk separators (`\n\n`)
- Chunk evidence content

### 4.3 Oversized Chunk Policy
When a candidate chunk exceeds the remaining token budget:
- **`skip` (Default)**: Safely omits the chunk from the context without exceeding the budget, preserving evidence integrity.
- **`truncate`**: Proportionally truncates the chunk content to fit within the remaining token allowance, appending an ellipsis (`...`).

---

## 5. Deduplication Rules

Deduplication operates in two stages:
1. **Primary Deduplication (`chunk_id`)**: A `seen_chunk_ids: set[str]` tracks identifiers. The first occurrence (highest rank) is retained; subsequent occurrences are discarded.
2. **Secondary Deduplication (Normalized Content)**: If `deduplicate_content=True`, Unicode NFKC normalization, lowercase conversion, and whitespace collapsing are applied. If identical content appears under a differing ID, subsequent occurrences are discarded.

---

## 6. Citation Model & Evidence Mapping

Each selected chunk produces a `Citation` and a `ContextChunk`:

```json
{
  "citation_id": "[1]",
  "chunk_id": "doc_leave_p4_chunk_0",
  "document_id": "doc_leave_123",
  "source": "leave_policy.pdf",
  "file_name": "leave_policy.pdf",
  "file_type": "pdf",
  "page": 3,
  "page_number": 4,
  "section": "Annual Leave"
}
```

Citation tags are assigned strictly **after** deduplication and selection. Discarded chunks never receive citation numbers.

---

## 7. Example Use Case

**Query**: `"How many casual leave days?"`

**Retrieved Chunks**:
1. `leave_policy.pdf`, page 4: `"Employees receive 12 casual leave days."` (Rank 1)
2. `hr_policy.pdf`, page 8: `"Leave requests must be submitted through the HR portal."` (Rank 2)
3. `leave_policy.pdf`, page 4: `"Employees receive 12 casual leave days."` (Rank 3 - Duplicate)

**Generated Context (`BuiltContext.context_text`)**:
```text
[1]
source: leave_policy.pdf
page: 4

Employees receive 12 casual leave days.

[2]
source: hr_policy.pdf
page: 8

Leave requests must be submitted through the HR portal.
```

The duplicate chunk is discarded and does not receive a citation tag.

---

## 8. Security, Privacy & Performance

- **Sensitive Data Handling**: Raw context content is **never** logged. The builder logs only telemetry metadata:
  ```text
  Context built: selected_chunks=2, token_count=48, budget=2000, dropped=1
  ```
- **Performance**: O(N) single-pass selection and duplicate checking using hash sets. No expensive cross-chunk pairwise semantic comparisons are executed.

---

## 9. Architecture Boundaries

The Context Builder's scope ends at producing the `BuiltContext`. It does **not**:
- Call external LLM APIs
- Construct system prompt templates or user chat histories
- Validate answer correctness or hallucination
- Generate natural language responses
