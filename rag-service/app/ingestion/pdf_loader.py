"""
PDF document loader.

Loads Portable Document Format (.pdf) files using pypdf and returns a Document instance.

Cleaning behaviour
------------------
* Line endings normalised to \\n.
* Null bytes (\\x00) stripped.
* Leading/trailing whitespace stripped from each page and from the document as a whole,
  preserving paragraph structure.
* Page count and per-page metrics preserved in metadata for downstream citations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.base import BaseLoader
from app.ingestion.models import Document

logger = logging.getLogger(__name__)


class PDFLoader(BaseLoader):
    """
    Loader for PDF (.pdf) files.

    Usage::

        loader = PDFLoader()
        doc = loader.load(Path("policy.pdf"))

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the extension is not .pdf, if the file cannot be parsed,
                    or if the document contains no extractable text.
    """

    supported_extensions: frozenset[str] = frozenset({"pdf"})

    def load(self, file_path: Path | str) -> Document:
        """
        Load a .pdf file and return a Document.

        Args:
            file_path: Path to the .pdf file.

        Returns:
            Document with the file's extracted text content and metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is unsupported, the PDF is corrupted,
                        or no text could be extracted.
        """
        path = Path(file_path)
        logger.info("PDFLoader invoked: path=%s", path)

        self._validate_file(path)

        try:
            reader = PdfReader(str(path))
            num_pages = len(reader.pages)
        except (PdfReadError, Exception) as exc:
            raise ValueError(f"Failed to read or parse PDF file '{path}': {exc}") from exc

        page_texts: list[str] = []
        page_records: list[dict[str, Any]] = []

        for idx, page in enumerate(reader.pages):
            try:
                raw_text = page.extract_text() or ""
            except Exception as exc:
                logger.warning("Error extracting text from page %d of %s: %s", idx + 1, path, exc)
                raw_text = ""

            cleaned = self._clean(raw_text)
            if cleaned:
                page_texts.append(cleaned)
                page_records.append({
                    "page_index": idx,
                    "page_number": idx + 1,
                    "char_count": len(cleaned),
                })

        full_content = "\n\n".join(page_texts).strip()

        if not full_content:
            raise ValueError(f"Document is empty after loading: '{path}'")

        file_size = path.stat().st_size

        logger.info(
            "PDFLoader: successfully loaded file_name=%s size_bytes=%d pages=%d text_pages=%d",
            path.name,
            file_size,
            num_pages,
            len(page_records),
        )

        return Document(
            content=full_content,
            source=str(path.resolve()),
            file_name=path.name,
            file_type="pdf",
            metadata={
                "page_count": num_pages,
                "text_page_count": len(page_records),
                "pages": page_records,
                "size_bytes": file_size,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """
        Apply minimal, safe text cleaning.

        Steps:
            1. Strip null bytes.
            2. Normalise line endings to \\n.
            3. Trim trailing/leading whitespace per line and outer whitespace.
        """
        text = text.replace("\x00", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()
