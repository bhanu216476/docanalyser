"""Text cleanup utilities for document ingestion."""

import re


def clean_text(text: str) -> str:
    """Normalize extracted document text without destroying structure or meaning.

    - Normalizes line endings to standard Unix line breaks (\\n).
    - Trims leading/trailing whitespace from each line and from internal tabs/spaces.
    - Reduces consecutive blank lines (3 or more \\n) to double \\n to preserve paragraphs.
    - Strips leading and trailing whitespace from the complete string.
    - Preserves single newlines, punctuation, Unicode characters, and paragraph breaks.
    """
    if not text:
        return ""

    # 1. Normalize Windows/Mac line endings to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Process line by line: collapse repeated spaces/tabs and strip each line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 3. Collapse 3 or more consecutive newlines into 2 (preserving paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Strip overall text
    return text.strip()
