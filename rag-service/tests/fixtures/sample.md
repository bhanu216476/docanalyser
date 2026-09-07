# Sample Markdown Document

This is a sample document for testing the **MarkdownLoader**.

## Key Sections

- **Section 1**: Ingestion abstraction layer
- **Section 2**: Text normalization
- **Section 3**: Preservation of semantic hierarchy

### Code Block Example

```python
from app.ingestion import MarkdownLoader

loader = MarkdownLoader()
doc = loader.load("sample.md")
print(doc.file_name)
```
