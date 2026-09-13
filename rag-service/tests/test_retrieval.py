"""Tests for the in-memory dense retrieval layer."""

import math

import pytest
from pydantic import ValidationError

from app.embeddings import EmbeddingService, FakeEmbeddingProvider
from app.embeddings.models import EmbeddedChunk
from app.retrieval import (
    DenseRetrievalService,
    RetrievalFilter,
    RetrievalResult,
    cosine_similarity,
)


@pytest.fixture
def service() -> DenseRetrievalService:
    return DenseRetrievalService()


def _chunk(
    chunk_id: str,
    vector: list[float],
    content: str | None = None,
    metadata: dict[str, object] | None = None,
) -> EmbeddedChunk:
    chunk_metadata = metadata if metadata is not None else {
        "source": "test.md",
        "chunk_id": chunk_id,
    }
    return EmbeddedChunk(
        index=0,
        embedding=vector,
        token_count=1,
        chunk_id=chunk_id,
        content=content or f"Content for {chunk_id}",
        metadata=chunk_metadata,
    )


def test_cosine_similarity_basic_cases() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_zero_vectors_are_safe_and_finite() -> None:
    score = cosine_similarity([0.0, 0.0], [1.0, 0.0])
    assert score == 0.0
    assert math.isfinite(score)


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ([], [1.0], "first vector cannot be empty"),
        ([1.0], [], "second vector cannot be empty"),
        ([1.0], [1.0, 2.0], "dimensions must match"),
        ([math.nan], [1.0], "finite values"),
        ([math.inf], [1.0], "finite values"),
    ],
)
def test_cosine_similarity_rejects_invalid_vectors(
    first: list[float], second: list[float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cosine_similarity(first, second)


def test_empty_candidates_return_empty(service: DenseRetrievalService) -> None:
    assert service.retrieve([1.0, 0.0], []) == []


def test_retrieval_ranks_by_similarity_and_preserves_source(service: DenseRetrievalService) -> None:
    candidates = [
        _chunk("low", [0.6, 0.8]),
        _chunk("high", [1.0, 0.0], "Original high content"),
        _chunk("middle", [0.8, 0.6]),
    ]

    results = service.retrieve([1.0, 0.0], candidates)

    assert [result.chunk_id for result in results] == ["high", "middle", "low"]
    assert results[0].content == "Original high content"
    assert results[0].metadata == {"source": "test.md", "chunk_id": "high"}
    assert [result.rank for result in results] == [1, 2, 3]
    assert all(math.isfinite(result.score) for result in results)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True, False])
def test_top_k_must_be_positive_integer(
    service: DenseRetrievalService, top_k: object
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        service.retrieve([1.0, 0.0], [], top_k=top_k)  # type: ignore[arg-type]


def test_top_k_limits_results_and_allows_short_candidate_lists(
    service: DenseRetrievalService,
) -> None:
    candidates = [_chunk(str(index), [1.0, 0.0]) for index in range(3)]

    assert len(service.retrieve([1.0, 0.0], candidates, top_k=1)) == 1
    assert len(service.retrieve([1.0, 0.0], candidates, top_k=3)) == 3
    assert len(service.retrieve([1.0, 0.0], candidates, top_k=10)) == 3


def test_equal_scores_use_stable_input_order(service: DenseRetrievalService) -> None:
    candidates = [_chunk("first", [1.0, 0.0]), _chunk("second", [1.0, 0.0])]

    results = service.retrieve([1.0, 0.0], candidates)

    assert [result.chunk_id for result in results] == ["first", "second"]


@pytest.mark.parametrize("threshold", [math.nan, math.inf, -math.inf, "0.5", True])
def test_score_threshold_must_be_finite_numeric(
    service: DenseRetrievalService, threshold: object
) -> None:
    with pytest.raises(ValueError, match="score_threshold"):
        service.retrieve([1.0, 0.0], [], score_threshold=threshold)  # type: ignore[arg-type]


def test_score_threshold_is_inclusive(service: DenseRetrievalService) -> None:
    candidate = _chunk("exact", [0.8, 0.6])

    results = service.retrieve([1.0, 0.0], [candidate], score_threshold=0.8)

    assert [result.chunk_id for result in results] == ["exact"]


def test_score_threshold_can_remove_all_results(service: DenseRetrievalService) -> None:
    results = service.retrieve(
        [1.0, 0.0], [_chunk("candidate", [1.0, 0.0])], score_threshold=1.1
    )

    assert results == []


def test_top_k_is_applied_before_inclusive_threshold(service: DenseRetrievalService) -> None:
    candidates = [
        _chunk("A", [1.0, 0.0]),
        _chunk("B", [0.95, 0.3122498999]),
        _chunk("C", [0.76, 0.6499230724]),
        _chunk("D", [0.6, 0.8]),
        _chunk("E", [0.4, 0.916515139]),
    ]

    first = service.retrieve([1.0, 0.0], candidates, top_k=3, score_threshold=0.70)
    second = service.retrieve([1.0, 0.0], candidates, top_k=5, score_threshold=0.80)

    assert [result.chunk_id for result in first] == ["A", "B", "C"]
    assert [result.chunk_id for result in second] == ["A", "B"]


def test_retrieval_result_rejects_non_finite_scores() -> None:
    with pytest.raises(ValidationError, match="score must be finite"):
        RetrievalResult(chunk_id="x", content="content", score=math.nan, rank=1)


def test_retrieve_text_reuses_existing_embedding_service(
    service: DenseRetrievalService,
) -> None:
    provider = FakeEmbeddingProvider(dimension=2)
    embedding_service = EmbeddingService(
        provider=provider,
        sleep_fn=lambda _: None,
    )
    query_vector = embedding_service.embed_texts(["query"])[0].embedding
    candidate = _chunk("query-chunk", query_vector)

    results = service.retrieve_text("query", [candidate], embedding_service)

    assert [result.chunk_id for result in results] == ["query-chunk"]
    assert provider.call_count == 2


def test_no_filters_return_all_candidates(service: DenseRetrievalService) -> None:
    candidates = [_chunk("one", [1.0, 0.0]), _chunk("two", [0.9, 0.4358898944])]

    results = service.retrieve([1.0, 0.0], candidates, top_k=5, filters=RetrievalFilter())

    assert [result.chunk_id for result in results] == ["one", "two"]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (RetrievalFilter(document_id="doc-1"), ["one", "three"]),
        (RetrievalFilter(file_type="pdf"), ["one", "four"]),
        (RetrievalFilter(source="report.pdf"), ["one"]),
        (RetrievalFilter(document_id="doc-1", file_type="pdf"), ["one"]),
    ],
)
def test_metadata_filters_use_deterministic_and_semantics(
    service: DenseRetrievalService,
    filters: RetrievalFilter,
    expected: list[str],
) -> None:
    candidates = [
        _chunk("one", [1.0, 0.0], metadata={
            "document_id": "doc-1", "file_type": "pdf", "source": "report.pdf"
        }),
        _chunk("two", [0.9, 0.4358898944], metadata={
            "document_id": "doc-2", "file_type": "md", "source": "notes.md"
        }),
        _chunk("three", [0.8, 0.6], metadata={
            "document_id": "doc-1", "file_type": "md", "source": "notes.md"
        }),
        _chunk("four", [0.7, 0.7141428429], metadata={
            "document_id": "doc-3", "file_type": "pdf", "source": "other.pdf"
        }),
    ]

    results = service.retrieve([1.0, 0.0], candidates, top_k=5, filters=filters)

    assert [result.chunk_id for result in results] == expected


def test_missing_metadata_does_not_match(service: DenseRetrievalService) -> None:
    candidates = [
        _chunk("missing", [1.0, 0.0], metadata={"source": "test.md"}),
        _chunk("present", [0.9, 0.4358898944], metadata={"document_id": "doc-1"}),
    ]

    results = service.retrieve(
        [1.0, 0.0], candidates, filters=RetrievalFilter(document_id="doc-1")
    )

    assert [result.chunk_id for result in results] == ["present"]


def test_page_filter_matches_page_number_and_spanned_page_membership(
    service: DenseRetrievalService,
) -> None:
    candidates = [
        _chunk("single", [1.0, 0.0], metadata={"page_number": 5, "page": 4}),
        _chunk("spanned", [0.9, 0.4358898944], metadata={"page_numbers": [3, 5]}),
        _chunk("other", [0.8, 0.6], metadata={"page_number": 2, "page": 1}),
    ]

    results = service.retrieve(
        [1.0, 0.0], candidates, filters=RetrievalFilter(page_number=5)
    )

    assert [result.chunk_id for result in results] == ["single", "spanned"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"document_id": ""},
        {"document_id": "   "},
        {"file_type": ""},
        {"source": "   "},
        {"page_number": 0},
        {"unsupported": "value"},
    ],
)
def test_invalid_retrieval_filters_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RetrievalFilter(**kwargs)


def test_filters_do_not_mutate_original_metadata(service: DenseRetrievalService) -> None:
    metadata = {"document_id": "doc-1", "page_numbers": [1, 2]}
    original = {"document_id": "doc-1", "page_numbers": [1, 2]}
    candidate = _chunk("one", [1.0, 0.0], metadata=metadata)

    service.retrieve([1.0, 0.0], [candidate], filters=RetrievalFilter(page_number=2))

    assert metadata == original
    assert candidate.metadata == original


def test_provenance_extracts_supported_metadata_without_losing_original(
    service: DenseRetrievalService,
) -> None:
    metadata = {
        "document_id": "doc-1",
        "page": 4,
        "page_number": 5,
        "page_numbers": [4, 5],
        "headings": ["Results"],
        "source": "report.pdf",
        "file_type": "pdf",
        "custom": {"keep": True},
    }
    result = service.retrieve([1.0, 0.0], [_chunk("chunk-1", [1.0, 0.0], metadata=metadata)])[0]

    assert result.provenance is not None
    assert result.provenance.document_id == "doc-1"
    assert result.provenance.chunk_id == "chunk-1"
    assert result.provenance.page == 4
    assert result.provenance.page_number == 5
    assert result.provenance.page_numbers == [4, 5]
    assert result.provenance.headings == ["Results"]
    assert result.provenance.source == "report.pdf"
    assert result.provenance.file_type == "pdf"
    assert result.metadata == metadata
    assert result.metadata is not metadata


def test_missing_optional_provenance_is_safe(service: DenseRetrievalService) -> None:
    result = service.retrieve([1.0, 0.0], [_chunk("minimal", [1.0, 0.0], metadata={})])[0]

    assert result.provenance is not None
    assert result.provenance.chunk_id == "minimal"
    assert result.provenance.document_id is None
    assert result.provenance.page_numbers is None
    assert result.provenance.headings is None


def test_filters_apply_before_top_k_and_threshold(service: DenseRetrievalService) -> None:
    candidates = [
        _chunk("excluded-high", [1.0, 0.0], metadata={"document_id": "other"}),
        _chunk("kept-high", [0.95, 0.3122498999], metadata={"document_id": "doc-1"}),
        _chunk("kept-low", [0.7, 0.7141428429], metadata={"document_id": "doc-1"}),
    ]

    results = service.retrieve(
        [1.0, 0.0],
        candidates,
        top_k=2,
        score_threshold=0.8,
        filters=RetrievalFilter(document_id="doc-1"),
    )

    assert [result.chunk_id for result in results] == ["kept-high"]
