"""Build structured evidence context from final reranked results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.context.models import ContextItem, StructuredContext
from app.reranking.models import RerankedResult


class ContextBuilder:
    """Convert already ordered reranker output into LLM-ready evidence."""

    def build(self, results: Sequence[RerankedResult]) -> StructuredContext:
        """Preserve the supplied order while building immutable context models."""

        if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
            raise TypeError("results must be a sequence of RerankedResult")
        if not all(isinstance(result, RerankedResult) for result in results):
            raise TypeError("results must be a sequence of RerankedResult")

        items = [
            self._build_item(result, position)
            for position, result in enumerate(results, 1)
        ]
        return StructuredContext(items=items, formatted_text=self._format_items(items))

    def _build_item(self, result: RerankedResult, position: int) -> ContextItem:
        provenance = result.provenance
        metadata = result.metadata
        document_id = (
            result.document_id
            or (provenance.document_id if provenance is not None else "")
            or _metadata_string(metadata, "document_id")
        )
        file_name = result.file_name or _metadata_string(metadata, "file_name")
        source = (
            result.source
            or (provenance.source if provenance is not None else "")
            or _metadata_string(metadata, "source")
        )
        section = result.section or _heading_section(provenance)
        pages = _page_numbers(result)

        return ContextItem(
            position=position,
            chunk_id=result.chunk_id,
            content=result.content,
            document_id=document_id,
            file_name=file_name,
            page_numbers=pages,
            section=section,
            source=source,
            citation=_citation(
                position=position,
                file_name=file_name,
                document_id=document_id,
                chunk_id=result.chunk_id,
                section=section,
                page_numbers=pages,
            ),
            reranked_rank=result.reranked_rank,
        )

    @staticmethod
    def _format_items(items: list[ContextItem]) -> str:
        return "\n\n".join(
            f"{item.citation}\nChunk ID: {item.chunk_id}\n\n{item.content}"
            for item in items
        )


def _page_numbers(result: RerankedResult) -> list[int]:
    provenance = result.provenance
    if provenance is not None:
        if provenance.page_numbers:
            return _unique(provenance.page_numbers)
        if _is_integer(provenance.page_number):
            return [provenance.page_number]
        if _is_integer(provenance.page):
            return [provenance.page + 1]

    metadata = result.metadata
    page_numbers = metadata.get("page_numbers")
    if isinstance(page_numbers, list) and page_numbers:
        valid_pages = [page for page in page_numbers if _is_integer(page)]
        if valid_pages:
            return _unique(valid_pages)
    page_number = metadata.get("page_number")
    if _is_integer(page_number):
        return [page_number]
    page = metadata.get("page")
    if _is_integer(page):
        return [page + 1]
    return []


def _citation(
    *,
    position: int,
    file_name: str,
    document_id: str,
    chunk_id: str,
    section: str | None,
    page_numbers: list[int],
) -> str:
    label = file_name or document_id or chunk_id
    parts = [label]
    if section:
        parts.append(section)
    if page_numbers:
        page_label = "p." if len(page_numbers) == 1 else "pp."
        parts.append(f"{page_label} {_format_pages(page_numbers)}")
    return f"[{position}] " + ", ".join(parts)


def _format_pages(page_numbers: list[int]) -> str:
    ranges: list[str] = []
    start = previous = page_numbers[0]
    for page in page_numbers[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


def _heading_section(provenance: Any) -> str | None:
    if provenance is None or not provenance.headings:
        return None
    headings = [heading for heading in provenance.headings if heading.strip()]
    return headings[-1] if headings else None


def _metadata_string(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) else ""


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _unique(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))