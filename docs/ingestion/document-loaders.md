# Document Loaders — Ingestion Pipeline

## Overview

Document loaders form the first layer of the DocAnalyser ingestion pipeline. Their sole responsibility is:

```text
FILE → VALIDATE & READ → CLEAN → DOCUMENT MODEL
```

Loaders extract raw content from heterogeneous file types on disk and map them into a standardized, immutable internal representation: the `Document` model.

> **Note**: Chunking, tokenization, embeddings generation, vector storage, and retrieval are strictly downstream stages and are **not** implemented in this layer.

---

## Ingestion Architecture

```text
Input File (.txt, .md, .markdown)
              ↓
File Validation (Existence, Extension, Encoding)
              ↓
Concrete Loader (TxtLoader / MarkdownLoader)
              ↓
Minimal Text Cleaning (Strip nulls, Normalize line endings, Trim outer whitespace)
              ↓
Document Model (content, source, file_name, file_type, metadata)
              ↓
[Future: Document Chunking Stage]
              ↓
[Future: Embeddings & Vector Storage (Qdrant)]
```

---

## Common Document Representation

Located in `app.ingestion.models.Document`.

```python
class Document(BaseModel):
    content: str               # Raw text content of the document
    source: str                # Absolute filesystem path of source file
    file_name: str             # Basename of the file (e.g., "report.txt")
    file_type: str             # Lowercase extension without dot ("txt", "md")
    metadata: dict[str, Any]   # Metadata dictionary (encoding, size_bytes, format, etc.)
```

### Key Properties:
- **Frozen (Immutable)**: `model_config = {"frozen": True}` prevents downstream mutations.
- **Extensible Metadata**: Flexible dictionary avoids schema lock-in before chunking requirements stabilize.

---

## Common Loader Interface (`BaseLoader`)

Located in `app.ingestion.base.BaseLoader`.

An abstract base class (ABC) that enforces the loading contract:

```python
class BaseLoader(ABC):
    supported_extensions: frozenset[str]

    @abstractmethod
    def load(self, file_path: Path) -> Document:
        """Loads file and returns Document."""
        ...
```

Subclasses share built-in validation via `_validate_file(file_path: Path)`.

### Adding New Loaders in the Future:
To support new formats (such as `.pdf`, `.docx`, `.html`):
1. Subclass `BaseLoader`.
2. Define `supported_extensions = frozenset({"pdf"})`.
3. Implement `load(self, file_path: Path) -> Document`.
4. No modification to existing loaders is needed (Open-Closed Principle).

---

## Supported Loaders & Behavior

### 1. TXT Loader (`TxtLoader`)

- **Supported Extensions**: `.txt`
- **Encoding**: Explicit UTF-8 (`encoding="utf-8"`).
- **Cleaning Behavior**:
  1. Strips null bytes (`\x00`).
  2. Normalizes line endings (`\r\n` and `\r` to `\n`).
  3. Strips outer leading/trailing whitespace while preserving paragraph breaks.
- **Metadata**:
  - `encoding`: `"utf-8"`
  - `size_bytes`: File size in bytes.

### 2. Markdown Loader (`MarkdownLoader`)

- **Supported Extensions**: `.md`, `.markdown`
- **Encoding**: Explicit UTF-8.
- **Handling Strategy — Option A (Preserve Markdown)**:
  - Preserves Markdown structure (headings `#`, lists `-`, emphasis `**bold**`, code blocks).
  - *Reasoning*: Structural syntax provides semantic hierarchy invaluable for future semantic chunking. Converting to plain text is a lossy transformation that should not happen at ingestion.
  - Zero third-party parsing dependencies required.
- **Metadata**:
  - `encoding`: `"utf-8"`
  - `size_bytes`: File size in bytes.
  - `format`: `"markdown"`

---

## Error Handling & Validation Rules

| Scenario | Exception | Behavior |
| :--- | :--- | :--- |
| **Missing file** | `FileNotFoundError` | Raised if file does not exist on disk |
| **Unsupported extension** | `ValueError` | Raised if file suffix is not in `supported_extensions` |
| **Empty file** | `ValueError` | Raised if document contains no text after cleaning |
| **Corrupted / Invalid encoding** | `UnicodeDecodeError` | Raised if file cannot be decoded using UTF-8 |

---

## Security Considerations

- File paths are treated as untrusted inputs.
- Only local file read operations are executed; no dynamic execution, evaluation, or shell invocations take place.
- Files are validated strictly against allowed extensions prior to reading.
