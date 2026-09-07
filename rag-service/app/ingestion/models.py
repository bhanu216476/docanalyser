"""
Document model for the ingestion pipeline.

Represents the common internal representation of a loaded document.
This model is the output of every loader and the input to the chunking stage.

Pipeline position:
    Loader → Document → Chunking → Embedding → Vector Store
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """
    Immutable representation of a loaded document.

    Fields are intentionally minimal — only what is genuinely needed
    by the current and near-future pipeline stages (chunking, embedding).

    Attributes:
        content:   Full raw text content of the document (preserved as loaded).
        source:    Absolute path string of the originating file.
        file_name: Basename of the originating file (e.g. ``report.txt``).
        file_type: Lowercase file extension without leading dot (e.g. ``txt``, ``md``).
        metadata:  Arbitrary key-value pairs for loader-specific or future metadata.
                   Kept generic to avoid premature schema lock-in.
    """

    content: str = Field(..., description="Full raw text content of the document.")
    source: str = Field(..., description="Absolute path of the source file.")
    file_name: str = Field(..., description="Basename of the source file.")
    file_type: str = Field(
        ..., description="File extension without leading dot, lowercase (e.g. 'txt', 'md')."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Loader-specific or pipeline metadata (e.g. encoding, size_bytes).",
    )

    model_config = {"frozen": True}
