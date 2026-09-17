from __future__ import annotations

import pytest

from app.context import ContextBuilder
from app.retrieval.models import RetrievalProvenance
from app.reranking.models import RerankedResult


def _result(
    chunk_id: str = "chunk-1",
    *,
    content: str = "Evidence text",
    rank: int = 1,
    **kwargs: object,
) -> RerankedResult:
    values: dict[str, object] = {
        "document_id": "doc-1",
        "file_name": "paper.pdf",
        "source": "docs/paper.pdf",
    }
    values.update(kwargs)
    return RerankedResult(
        chunk_id=chunk_id,
        content=content,
        retrieval_score=0.8,
        reranker_score=0.9,
        retrieval_rank=rank,
        reranked_rank=rank,
        rank_delta=0,
        **values,
    )


def test_empty_results() -> None:
    context = ContextBuilder().build([])
    assert context.items == []
    assert context.formatted_text == ""
    assert context.item_count == 0


def test_order_content_identity_and_determinism() -> None:
    results = [_result("B", rank=1), _result("A", rank=2, content="Unicode: cafe\u0301")]
    builder = ContextBuilder()
    first = builder.build(results)
    second = builder.build(results)

    assert [item.chunk_id for item in first.items] == ["B", "A"]
    assert [item.position for item in first.items] == [1, 2]
    assert first.items[1].content == "Unicode: cafe\u0301"
    assert first == second
    assert results[0].metadata == {}


def test_provenance_page_priority_and_heading_fallback() -> None:
    provenance = RetrievalProvenance(
        chunk_id="chunk-1",
        page=2,
        page_number=3,
        page_numbers=[3, 4, 4, 5],
        headings=["Introduction", "Retrieval"],
        source="provenance.pdf",
    )
    item = ContextBuilder().build([_result(provenance=provenance)]).items[0]

    assert item.page_numbers == [3, 4, 5]
    assert item.section == "Retrieval"
    assert item.source == "docs/paper.pdf"
    assert item.citation == "[1] paper.pdf, Retrieval, pp. 3-5"


@pytest.mark.parametrize(
    ("provenance", "expected"),
    [
        (RetrievalProvenance(chunk_id="x", page_number=4), [4]),
        (RetrievalProvenance(chunk_id="x", page=0), [1]),
        (RetrievalProvenance(chunk_id="x"), []),
    ],
)
def test_page_normalization(provenance: RetrievalProvenance, expected: list[int]) -> None:
    item = ContextBuilder().build([_result(provenance=provenance)]).items[0]
    assert item.page_numbers == expected


def test_metadata_page_fallback_and_missing_file_citation() -> None:
    result = _result(
        document_id="document-42",
        file_name="",
        metadata={"page": 6, "file_name": "", "document_id": "document-42"},
    )
    item = ContextBuilder().build([result]).items[0]

    assert item.page_numbers == [7]
    assert item.citation == "[1] document-42, p. 7"


def test_formatted_text_contains_only_ordered_evidence() -> None:
    results = [_result("first", content="  exact text  "), _result("second", rank=2)]
    formatted = ContextBuilder().build(results).formatted_text

    assert formatted == (
        "[1] paper.pdf\nChunk ID: first\n\n  exact text  \n\n"
        "[2] paper.pdf\nChunk ID: second\n\nEvidence text"
    )


def test_build_rejects_non_reranked_sequences() -> None:
    with pytest.raises(TypeError):
        ContextBuilder().build([object()])  # type: ignore[list-item]