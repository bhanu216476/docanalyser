"""Tests for the in-memory dense retrieval layer."""

import math

import pytest
from pydantic import ValidationError

from app.embeddings import EmbeddingService, FakeEmbeddingProvider
from app.embeddings.models import EmbeddedChunk
from app.retrieval import DenseRetrievalService, RetrievalResult, cosine_similarity


@pytest.fixture
def service() -> DenseRetrievalService:
    return DenseRetrievalService()


def _chunk(chunk_id: str, vector: list[float], content: str | None = None) -> EmbeddedChunk:
    return EmbeddedChunk(
        index=0,
        embedding=vector,
        token_count=1,
        chunk_id=chunk_id,
        content=content or f"Content for {chunk_id}",
        metadata={"source": "test.md", "chunk_id": chunk_id},
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
