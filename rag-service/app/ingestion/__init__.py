"""
Ingestion module for document loading, parsing, and preparation.

Exports:
    - Document: Common representation for loaded documents.
    - BaseLoader: Abstract base class for all file loaders.
    - TxtLoader: Plain text loader.
    - MarkdownLoader: Markdown file loader.
"""

from app.ingestion.base import BaseLoader
from app.ingestion.markdown_loader import MarkdownLoader
from app.ingestion.models import Document
from app.ingestion.txt_loader import TxtLoader

__all__ = [
    "Document",
    "BaseLoader",
    "TxtLoader",
    "MarkdownLoader",
]
