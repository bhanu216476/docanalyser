"""
Recursive and structure-aware document chunker.

Preserves semantic boundaries by recursively traversing a hierarchy of
separators (Markdown headings, paragraph breaks, line breaks, sentence
boundaries, whitespace, and character-level fallback).

For Markdown documents, structure is explicitly respected:
    - Top-level and nested headings are parsed into structural sections.
    - Breadcrumbs (e.g. ['Company Policies', 'Leave Policy']) are tracked.
    - Heading hierarchy is preserved in chunk metadata ('section', 'headings').
    - Empty sections do not produce empty chunks.
    - Oversized sections are recursively subdivided.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Sequence

from app.ingestion.chunking.base import BaseChunker
from app.ingestion.chunking.models import Chunk
from app.ingestion.models import Document

logger = logging.getLogger(__name__)

DEFAULT_RECURSIVE_CHUNK_SIZE: int = 1000
DEFAULT_RECURSIVE_OVERLAP: int = 200

# Default separator hierarchy from coarsest to finest semantic granularity
DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",       # Paragraph boundaries
    "\n",         # Line boundaries
    "SENTENCE",   # Sentence boundaries (.!?)
    " ",          # Word / whitespace boundaries
    "",           # Character fallback
)

_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_SENTENCE_REGEX = re.compile(r"(?<=[.!?])\s+")


class RecursiveChunker(BaseChunker):
    """
    Splits documents recursively using semantic separators and Markdown structure.

    Separator Hierarchy:
        1. Markdown headings (# through ######, when applicable)
        2. Paragraph boundaries (\\n\\n)
        3. Line boundaries (\\n)
        4. Sentence boundaries (.!?)
        5. Whitespace ( )
        6. Character fallback

    Args:
        chunk_size: Maximum character length of each chunk. Must be > 0.
        overlap: Character overlap between consecutive chunks. Must be >= 0 and < chunk_size.
        separators: Custom hierarchy of text separators. Defaults to standard hierarchy.

    Raises:
        ValueError: If chunk_size <= 0, overlap < 0, or overlap >= chunk_size.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_RECURSIVE_CHUNK_SIZE,
        overlap: int = DEFAULT_RECURSIVE_OVERLAP,
        separators: Optional[Sequence[str]] = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")
        if overlap < 0:
            raise ValueError(f"overlap must be a non-negative integer, got {overlap}")
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = list(separators) if separators is not None else list(DEFAULT_SEPARATORS)

    def chunk(self, document: Document) -> list[Chunk]:
        """
        Split a Document into ordered, structure-aware Chunks.

        Args:
            document: Loaded Document instance.

        Returns:
            List of ordered Chunk instances. If document is empty or whitespace only,
            returns an empty list.
        """
        text = document.content
        if not text or not text.strip():
            logger.debug(
                "RecursiveChunker: Document '%s' is empty or whitespace-only, returning 0 chunks.",
                document.file_name,
            )
            return []

        doc_id = self._resolve_document_id(document)

        # 1. Check if document should be processed with Markdown structure awareness
        is_markdown = (
            document.file_type.lower() == "md"
            or bool(_HEADING_REGEX.search(text))
        )

        if is_markdown:
            raw_chunks_data = self._chunk_markdown(text)
        else:
            raw_chunks_data = self._chunk_plain_text(text)

        # 2. Build Chunk models with metadata and character offset tracking
        chunks: list[Chunk] = []
        search_pos = 0

        for idx, item in enumerate(raw_chunks_data):
            chunk_content = item["content"]
            headings: list[str] = item.get("headings", [])
            section: str = item.get("section", "")

            # Locate character offsets in the original document content
            start_char: Optional[int] = None
            end_char: Optional[int] = None
            pos = text.find(chunk_content, search_pos)
            if pos != -1:
                start_char = pos
                end_char = pos + len(chunk_content)
                search_pos = max(search_pos, pos + max(1, len(chunk_content) - self.overlap))
            else:
                pos0 = text.find(chunk_content)
                if pos0 != -1:
                    start_char = pos0
                    end_char = pos0 + len(chunk_content)

            extra_meta: dict[str, Any] = {
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "strategy": "recursive",
            }
            if headings:
                extra_meta["headings"] = headings
            if section:
                extra_meta["section"] = section

            meta = self._build_chunk_metadata(
                document,
                chunk_index=idx,
                document_id=doc_id,
                extra_metadata=extra_meta,
            )

            chunks.append(
                Chunk(
                    chunk_id=self._generate_chunk_id(doc_id, idx),
                    document_id=doc_id,
                    content=chunk_content,
                    chunk_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=meta,
                )
            )

        logger.debug(
            "RecursiveChunker: generated %d chunks for document '%s'",
            len(chunks),
            document.file_name,
        )
        return chunks

    # ------------------------------------------------------------------
    # Markdown Section Parsing & Heading Tracking
    # ------------------------------------------------------------------

    def _chunk_markdown(self, text: str) -> list[dict[str, Any]]:
        """
        Partition Markdown text by headings and recursively chunk sections.

        Returns a list of dicts: {"content": str, "headings": list[str], "section": str}
        """
        matches = list(_HEADING_REGEX.finditer(text))
        if not matches:
            return self._chunk_plain_text(text)

        sections: list[dict[str, Any]] = []
        heading_stack: list[tuple[int, str]] = []

        # Preamble before first heading (if any)
        if matches[0].start() > 0:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                sections.append(
                    {"content": preamble, "headings": [], "section": ""}
                )

        # Process each heading and its bounded text
        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_raw = text[start:end]

            # Update heading stack
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

            current_headings = [h[1] for h in heading_stack]
            current_section = " > ".join(current_headings)

            # Check body text under this heading
            heading_line_len = len(match.group(0))
            body_text = section_raw[heading_line_len:].strip()

            # If section has no body text and is followed by another section,
            # avoid emitting an empty chunk (the heading is retained in the stack)
            if not body_text and i + 1 < len(matches):
                continue

            section_clean = section_raw.strip()
            if section_clean:
                sections.append(
                    {
                        "content": section_clean,
                        "headings": current_headings,
                        "section": current_section,
                    }
                )

        # If all sections had no body (e.g. document with only a title), emit the heading
        if not sections and matches:
            heading_title = matches[0].group(2).strip()
            sections.append(
                {
                    "content": text.strip(),
                    "headings": [heading_title],
                    "section": heading_title,
                }
            )

        # Recursively chunk each section if it exceeds chunk_size
        results: list[dict[str, Any]] = []
        for sec in sections:
            sec_content = sec["content"]
            if len(sec_content) <= self.chunk_size:
                results.append(sec)
            else:
                # Oversized section: recursively split using text separators
                sub_chunks = self._split_text(sec_content, self.separators)
                for sub in sub_chunks:
                    results.append(
                        {
                            "content": sub,
                            "headings": sec["headings"],
                            "section": sec["section"],
                        }
                    )

        return results

    # ------------------------------------------------------------------
    # Plain Text Recursive Splitting
    # ------------------------------------------------------------------

    def _chunk_plain_text(self, text: str) -> list[dict[str, Any]]:
        """Split plain text recursively without heading hierarchy."""
        sub_chunks = self._split_text(text, self.separators)
        return [{"content": c, "headings": [], "section": ""} for c in sub_chunks]

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """
        Recursively divide text using the separator hierarchy until all pieces fit.
        """
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        # Find the first applicable separator in text
        chosen_sep: Optional[str] = None
        remaining_seps: list[str] = []

        for idx, sep in enumerate(separators):
            if sep == "":
                chosen_sep = ""
                remaining_seps = []
                break
            elif sep == "SENTENCE":
                if _SENTENCE_REGEX.search(text):
                    chosen_sep = sep
                    remaining_seps = separators[idx + 1 :]
                    break
            elif sep in text:
                chosen_sep = sep
                remaining_seps = separators[idx + 1 :]
                break

        # Fallback to character slicing if no separator works or "" reached
        if chosen_sep is None or chosen_sep == "":
            return self._slice_characters(text)

        # Split using the chosen separator
        if chosen_sep == "SENTENCE":
            raw_splits = _SENTENCE_REGEX.split(text)
            join_str = " "
        else:
            raw_splits = text.split(chosen_sep)
            join_str = chosen_sep

        # Recursively divide any individual segment that exceeds chunk_size
        refined_splits: list[str] = []
        for s in raw_splits:
            s_clean = s.strip()
            if not s_clean:
                continue
            if len(s_clean) > self.chunk_size:
                sub_parts = self._split_text(s_clean, remaining_seps)
                refined_splits.extend(sub_parts)
            else:
                refined_splits.append(s_clean)

        # Merge segments up to chunk_size with overlap
        return self._merge_splits(refined_splits, join_str)

    def _merge_splits(self, splits: list[str], join_str: str) -> list[str]:
        """
        Combine small text segments into chunks <= chunk_size while respecting overlap.
        """
        if not splits:
            return []

        chunks: list[str] = []
        current_splits: list[str] = []
        current_len = 0

        for piece in splits:
            added_len = len(piece) if not current_splits else len(join_str) + len(piece)

            if current_len + added_len <= self.chunk_size:
                current_splits.append(piece)
                current_len += added_len
            else:
                # Finalize the current chunk
                if current_splits:
                    chunks.append(join_str.join(current_splits))

                # Calculate overlap splits for the start of the next chunk
                overlap_splits: list[str] = []
                overlap_len = 0

                if self.overlap > 0 and current_splits:
                    for s in reversed(current_splits):
                        extra = len(s) if not overlap_splits else len(s) + len(join_str)
                        if overlap_len + extra <= self.overlap:
                            overlap_splits.insert(0, s)
                            overlap_len += extra
                        else:
                            break

                # Ensure overlap plus new piece does not exceed chunk_size
                while (
                    overlap_splits
                    and (overlap_len + len(join_str) + len(piece)) > self.chunk_size
                ):
                    popped = overlap_splits.pop(0)
                    overlap_len -= (
                        len(popped)
                        if not overlap_splits
                        else len(popped) + len(join_str)
                    )

                current_splits = overlap_splits + [piece]
                current_len = len(join_str.join(current_splits))

        if current_splits:
            chunks.append(join_str.join(current_splits))

        return [c for c in chunks if c.strip()]

    def _slice_characters(self, text: str) -> list[str]:
        """Fallback character-level slicing when semantic boundaries are unavailable."""
        step = max(1, self.chunk_size - self.overlap)
        slices: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            c = text[start:end].strip()
            if c:
                slices.append(c)
            if end >= text_len:
                break
            start += step

        return slices
