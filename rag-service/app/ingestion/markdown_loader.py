"""
Markdown document loader.

Loads Markdown (``.md``, ``.markdown``) files and returns a ``Document`` instance.

Engineering Decision: Option A — Preserve Markdown Syntax
---------------------------------------------------------
Markdown structure (headings, lists, bold/italics, code blocks) is preserved as raw Markdown.
Reasoning:
1. Markdown structure carries semantic layout and hierarchy (e.g. ``# Header``, ``## Subheader``)
   that is vital for chunking and document structure analysis in later stages.
2. Converting Markdown to plain text is a lossy, irreversible transformation.
3. Preserving the original syntax avoids unnecessary external dependencies (keeping requirements minimal).

Cleaning behaviour
------------------
* Normalises line endings to ``\\n`` (handles ``\\r\\n`` and ``\\r``).
* Strips null bytes (``\\x00``).
* Strips leading/trailing whitespace from the document while preserving internal Markdown formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.ingestion.base import BaseLoader
from app.ingestion.models import Document

logger = logging.getLogger(__name__)


class MarkdownLoader(BaseLoader):
    """
    Loader for Markdown (``.md``, ``.markdown``) files.

    Preserves Markdown syntax to retain semantic structure for downstream processing.

    Usage::

        loader = MarkdownLoader()
        doc = loader.load(Path("README.md"))

    Raises:
        FileNotFoundError: File does not exist.
        ValueError: Extension is unsupported or file is empty.
        UnicodeDecodeError: File cannot be decoded as UTF-8.
    """

    supported_extensions: frozenset[str] = frozenset({"md", "markdown"})

    def load(self, file_path: Path) -> Document:
        """
        Load a Markdown file and return a ``Document``.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            ``Document`` containing raw Markdown content and metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the extension is unsupported or file is empty.
            UnicodeDecodeError: If decoding fails as UTF-8.
        """
        file_path = Path(file_path)
        logger.info("MarkdownLoader invoked: path=%s", file_path)

        self._validate_file(file_path)

        try:
            raw = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise UnicodeDecodeError(
                exc.encoding,
                exc.object,
                exc.start,
                exc.end,
                f"Failed to decode '{file_path}' as UTF-8: {exc.reason}",
            ) from exc

        content = self._clean(raw)

        if not content:
            raise ValueError(
                f"Document is empty after loading: '{file_path}'"
            )

        logger.info(
            "MarkdownLoader: successfully loaded file_name=%s size_bytes=%d",
            file_path.name,
            file_path.stat().st_size,
        )

        # Normalize file_type to 'md' or 'markdown' based on extension
        ext = file_path.suffix.lstrip(".").lower()

        return Document(
            content=content,
            source=str(file_path.resolve()),
            file_name=file_path.name,
            file_type=ext,
            metadata={
                "encoding": "utf-8",
                "size_bytes": file_path.stat().st_size,
                "format": "markdown",
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """
        Apply minimal, safe text cleaning while preserving Markdown formatting.

        Steps:
            1. Strip null bytes.
            2. Normalise line endings to ``\\n``.
            3. Strip outer whitespace while preserving internal structure.
        """
        text = text.replace("\x00", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()
