"""
Abstract base class for all document loaders.

Defines the contract that every concrete loader must satisfy.
New loaders (PDFLoader, DOCXLoader, HTMLLoader, …) must subclass
``BaseLoader`` and implement ``load()``.

Design:
    - Uses Python ``abc.ABC`` — simpler than Protocol for this use-case
      because we want both interface enforcement AND shared helper methods.
    - A single ``load()`` method is the full public API of a loader.
    - The ``supported_extensions`` class attribute is declared here as an
      abstract contract; each subclass must define it.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.ingestion.models import Document

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """
    Common abstraction for document loaders.

    Subclasses must implement:
        - ``supported_extensions``: frozenset of lowercase extensions
          without leading dot (e.g. ``frozenset({"txt"})``)
        - ``load(file_path)``: load the file and return a ``Document``

    Example usage::

        loader = TxtLoader()
        doc = loader.load(Path("report.txt"))
    """

    # Each subclass declares which extensions it handles.
    # Using a class-level frozenset makes extension checks O(1) and
    # prevents accidental mutation.
    supported_extensions: frozenset[str]

    @abstractmethod
    def load(self, file_path: Path) -> Document:
        """
        Load a document from ``file_path`` and return a ``Document``.

        Args:
            file_path: Path to the document file.

        Returns:
            A ``Document`` instance with content and metadata populated.

        Raises:
            FileNotFoundError: If ``file_path`` does not exist.
            ValueError: If the file extension is not supported by this loader,
                        or if the file is empty.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.
        """
        ...  # pragma: no cover

    # ------------------------------------------------------------------
    # Protected helpers available to all subclasses
    # ------------------------------------------------------------------

    def _validate_file(self, file_path: Path) -> None:
        """
        Perform common pre-load validation.

        Checks:
            1. File exists.
            2. Extension is in ``self.supported_extensions``.

        Args:
            file_path: Path to validate.

        Raises:
            FileNotFoundError: File does not exist.
            ValueError: Extension not supported.
        """
        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: '{file_path}'"
            )
        extension = file_path.suffix.lstrip(".").lower()
        if extension not in self.supported_extensions:
            supported = ", ".join(f".{e}" for e in sorted(self.supported_extensions))
            raise ValueError(
                f"Unsupported file extension '.{extension}' for {type(self).__name__}. "
                f"Supported: {supported}"
            )
        logger.debug(
            "Validated file: path=%s extension=%s loader=%s",
            file_path,
            extension,
            type(self).__name__,
        )
