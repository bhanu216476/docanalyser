"""
TXT document loader.

Loads plain-text (``.txt``) files and returns a ``Document`` instance.

Cleaning behaviour
------------------
Only minimal, safe transformations are applied:

* Line endings normalised to ``\\n`` (handles ``\\r\\n`` and ``\\r``).
* Null bytes (``\\x00``) stripped — these occasionally appear in files
  produced by Windows tools and would corrupt downstream processing.
* Leading/trailing whitespace stripped from the document as a whole,
  but internal paragraph structure is preserved.

Nothing else is modified.  Lowercasing, punctuation removal, stop-word
removal, tokenisation, and chunking are all out of scope for this stage.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.ingestion.base import BaseLoader
from app.ingestion.models import Document

logger = logging.getLogger(__name__)


class TxtLoader(BaseLoader):
    """
    Loader for plain-text (``.txt``) files.

    Usage::

        loader = TxtLoader()
        doc = loader.load(Path("report.txt"))

    Raises:
        FileNotFoundError: File does not exist.
        ValueError:         Extension is not ``.txt``, or the file is empty.
        UnicodeDecodeError: File cannot be decoded as UTF-8.
    """

    supported_extensions: frozenset[str] = frozenset({"txt"})

    def load(self, file_path: Path) -> Document:
        """
        Load a ``.txt`` file and return a ``Document``.

        Args:
            file_path: Path to the ``.txt`` file.

        Returns:
            ``Document`` with the file's text content and metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the extension is unsupported or the file is empty.
            UnicodeDecodeError: If the file contains non-UTF-8 bytes.
        """
        file_path = Path(file_path)  # Coerce str → Path defensively
        logger.info("TxtLoader invoked: path=%s", file_path)

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
            "TxtLoader: successfully loaded file_name=%s size_bytes=%d",
            file_path.name,
            file_path.stat().st_size,
        )

        return Document(
            content=content,
            source=str(file_path.resolve()),
            file_name=file_path.name,
            file_type="txt",
            metadata={
                "encoding": "utf-8",
                "size_bytes": file_path.stat().st_size,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """
        Apply minimal, safe text cleaning.

        Steps (in order):
            1. Strip null bytes.
            2. Normalise line endings to ``\\n``.
            3. Strip leading/trailing whitespace from the whole document.

        Args:
            text: Raw file contents.

        Returns:
            Cleaned text string.
        """
        # 1. Remove null bytes (safe; they are never meaningful in prose text)
        text = text.replace("\x00", "")

        # 2. Normalise Windows (\\r\\n) and old Mac (\\r) line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Strip surrounding whitespace only — preserve internal structure
        return text.strip()
