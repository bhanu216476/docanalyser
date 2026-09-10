"""
Tests for the Embedding Service.

Covers:
    - Batching: empty input, small, equal, large, order preservation, chunk embedding.
    - Token limits: within limit, exact limit, over limit, pre-call validation, chunk index reporting.
    - Retry logic: transient failures, exponential backoff, retries exhausted, permanent failures, jitter.
    - Validation: empty/whitespace/non-string inputs, invalid service constructor configs.
    - Provider contract: wrong count, non-list, empty vector, non-numeric elements.
    - Token counters and factories: CharApproxTokenCounter, make_token_counter, create_embedding_service.
    - Data models: EmbeddingRequest and EmbeddingResult immutability and validations.

All tests use FakeEmbeddingProvider and a no-op sleep function (sleep_fn=lambda _: None)
for fast, zero-delay, deterministic execution without network calls.
"""

import math
from typing import Sequence
import pytest
from pydantic import ValidationError

from app.embeddings import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RETRY_BASE_DELAY,
    CharApproxTokenCounter,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingRetryExhaustedError,
    EmbeddingService,
    EmbeddingTokenLimitError,
    EmbeddingValidationError,
    FakeEmbeddingProvider,
    TokenCounter,
    create_embedding_service,
    make_token_counter,
)
from app.ingestion.chunking.models import Chunk


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def fake_provider() -> FakeEmbeddingProvider:
    """Standard fake provider returning 8-dimensional vectors."""
    return FakeEmbeddingProvider(dimension=8)


@pytest.fixture
def noop_sleep():
    """Zero-delay sleep fixture for instant retries."""
    return lambda _: None


@pytest.fixture
def service(fake_provider: FakeEmbeddingProvider, noop_sleep) -> EmbeddingService:
    """Standard service with small batch size for testing batch logic."""
    return EmbeddingService(
        provider=fake_provider,
        batch_size=5,
        max_tokens=100,
        max_retries=3,
        retry_base_delay=1.0,
        sleep_fn=noop_sleep,
    )


# ======================================================================
# 1. Batching Tests
# ======================================================================

class TestEmbeddingBatching:
    """Tests for batch splitting, sizing, and order preservation."""

    def test_empty_input_returns_empty_list(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Empty input list returns [] immediately without calling the provider."""
        results = service.embed_texts([])
        assert results == []
        assert fake_provider.call_count == 0

    def test_input_smaller_than_batch_size(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Input size < batch_size produces exactly 1 batch of matching size."""
        texts = ["Text one", "Text two", "Text three"]  # 3 texts, batch_size=5
        results = service.embed_texts(texts)

        assert len(results) == 3
        assert fake_provider.call_count == 1
        assert len(fake_provider.received_batches) == 1
        assert fake_provider.received_batches[0] == texts
        for idx, res in enumerate(results):
            assert res.index == idx
            assert len(res.embedding) == 8
            assert res.token_count > 0

    def test_input_equal_to_batch_size(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Input size == batch_size produces exactly 1 full batch."""
        texts = [f"Item {i}" for i in range(5)]
        results = service.embed_texts(texts)

        assert len(results) == 5
        assert fake_provider.call_count == 1
        assert len(fake_provider.received_batches[0]) == 5
        assert [r.index for r in results] == list(range(5))

    def test_input_larger_than_batch_size(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Input size > batch_size splits into ceil(N/batch_size) batches with correct sizes."""
        texts = [f"Chunk content {i}" for i in range(12)]  # 12 items, batch_size=5 -> batches: 5, 5, 2
        results = service.embed_texts(texts)

        assert len(results) == 12
        assert fake_provider.call_count == 3
        assert len(fake_provider.received_batches[0]) == 5
        assert len(fake_provider.received_batches[1]) == 5
        assert len(fake_provider.received_batches[2]) == 2
        assert [r.index for r in results] == list(range(12))

    def test_preserves_input_order(self, service: EmbeddingService):
        """Results preserve the original input sequence regardless of batch boundaries."""
        texts = [f"Unique paragraph #{i}" for i in range(17)]
        results = service.embed_texts(texts)

        assert len(results) == 17
        for expected_idx, result in enumerate(results):
            assert result.index == expected_idx

    def test_embed_chunks_convenience_wrapper(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """embed_chunks extracts chunk.content and returns results mapped to chunks in order."""
        chunks = [
            Chunk(
                chunk_id=f"doc-123:{i}",
                content=f"Content for chunk {i}",
                chunk_index=i,
                document_id="doc-123",
                metadata={"source": "test.txt"},
            )
            for i in range(7)
        ]
        results = service.embed_chunks(chunks)

        assert len(results) == 7
        assert fake_provider.call_count == 2  # 5 + 2
        for idx, res in enumerate(results):
            assert res.index == idx
            assert len(res.embedding) == 8

    def test_embed_chunks_empty(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """embed_chunks with empty list returns [] without calling provider."""
        results = service.embed_chunks([])
        assert results == []
        assert fake_provider.call_count == 0


# ======================================================================
# 2. Token Limit Tests
# ======================================================================

class TestEmbeddingTokenLimits:
    """Tests for token limit checking and pre-call enforcement."""

    def test_text_within_token_limit(self, service: EmbeddingService):
        """Text well within token limit is processed successfully."""
        results = service.embed_texts(["Short text"])
        assert len(results) == 1
        assert results[0].token_count <= 100

    def test_text_at_exact_token_limit(self, fake_provider: FakeEmbeddingProvider, noop_sleep):
        """Text whose token count is exactly equal to max_tokens is accepted."""
        # Using CharApproxTokenCounter: ceil(len / 4)
        # 40 characters -> 10 tokens
        exact_text = "A" * 40
        service = EmbeddingService(
            provider=fake_provider,
            max_tokens=10,
            token_counter=CharApproxTokenCounter(),
            sleep_fn=noop_sleep,
        )
        results = service.embed_texts([exact_text])
        assert len(results) == 1
        assert results[0].token_count == 10

    def test_text_exceeding_token_limit_raises_error(self, fake_provider: FakeEmbeddingProvider, noop_sleep):
        """Text exceeding token limit raises EmbeddingTokenLimitError."""
        # 44 characters -> 11 tokens (> 10)
        too_long_text = "A" * 44
        service = EmbeddingService(
            provider=fake_provider,
            max_tokens=10,
            token_counter=CharApproxTokenCounter(),
            sleep_fn=noop_sleep,
        )

        with pytest.raises(EmbeddingTokenLimitError) as exc_info:
            service.embed_texts([too_long_text])

        err = exc_info.value
        assert err.chunk_index == 0
        assert err.token_count == 11
        assert err.max_tokens == 10
        assert "exceeds token limit" in str(err)

    def test_provider_not_called_when_token_limit_exceeded(
        self, fake_provider: FakeEmbeddingProvider, noop_sleep
    ):
        """CRITICAL: Token validation runs upfront before any provider call is made."""
        too_long_text = "B" * 500  # 125 tokens (> 100)
        service = EmbeddingService(
            provider=fake_provider,
            max_tokens=100,
            sleep_fn=noop_sleep,
        )

        with pytest.raises(EmbeddingTokenLimitError):
            service.embed_texts([too_long_text])

        # Provider must NOT have been called
        assert fake_provider.call_count == 0

    def test_middle_chunk_exceeds_token_limit_aborts_immediately(
        self, fake_provider: FakeEmbeddingProvider, noop_sleep
    ):
        """If chunk at index 2 exceeds the limit, error specifies index 2 and 0 calls occur."""
        service = EmbeddingService(
            provider=fake_provider,
            max_tokens=20,
            token_counter=CharApproxTokenCounter(),
            sleep_fn=noop_sleep,
        )
        texts = [
            "Valid short text 0",  # ~5 tokens
            "Valid short text 1",  # ~5 tokens
            "X" * 120,             # 30 tokens (> 20) -> VIOLATION at index 2
            "Valid short text 3",  # ~5 tokens
        ]

        with pytest.raises(EmbeddingTokenLimitError) as exc_info:
            service.embed_texts(texts)

        assert exc_info.value.chunk_index == 2
        assert fake_provider.call_count == 0


# ======================================================================
# 3. Retry Logic Tests
# ======================================================================

class TestEmbeddingRetryLogic:
    """Tests for exponential backoff, jitter, and error classification."""

    def test_transient_error_succeeds_on_first_retry(self, noop_sleep):
        """Transient error on call 1 retries and succeeds on call 2."""
        provider = FakeEmbeddingProvider(fail_on_calls={1})
        service = EmbeddingService(
            provider=provider,
            batch_size=5,
            max_retries=3,
            sleep_fn=noop_sleep,
        )

        results = service.embed_texts(["Hello world"])
        assert len(results) == 1
        assert provider.call_count == 2

    def test_multiple_transient_errors_succeed_before_exhaustion(self, noop_sleep):
        """Transient errors on calls 1 and 2 succeed on call 3 (within max_retries=3)."""
        provider = FakeEmbeddingProvider(fail_on_calls={1, 2})
        service = EmbeddingService(
            provider=provider,
            batch_size=5,
            max_retries=3,
            sleep_fn=noop_sleep,
        )

        results = service.embed_texts(["Chunk 1", "Chunk 2"])
        assert len(results) == 2
        assert provider.call_count == 3

    def test_retries_exhausted_raises_retry_exhausted_error(self, noop_sleep):
        """Failing all attempts raises EmbeddingRetryExhaustedError with attempt context."""
        # max_retries=2 -> total attempts = 3 (call 1 + 2 retries)
        provider = FakeEmbeddingProvider(fail_on_calls={1, 2, 3, 4})
        service = EmbeddingService(
            provider=provider,
            batch_size=5,
            max_retries=2,
            sleep_fn=noop_sleep,
        )

        with pytest.raises(EmbeddingRetryExhaustedError) as exc_info:
            service.embed_texts(["Should fail"])

        err = exc_info.value
        assert err.attempts == 3
        assert err.batch_index == 0
        assert isinstance(err.cause, EmbeddingProviderError)
        assert err.cause.is_transient is True
        assert provider.call_count == 3

    def test_permanent_error_fails_immediately_without_retries(self, noop_sleep):
        """Non-transient EmbeddingProviderError is NOT retried (call_count == 1)."""
        provider = FakeEmbeddingProvider(permanent_fail_on_calls={1})
        service = EmbeddingService(
            provider=provider,
            max_retries=3,
            sleep_fn=noop_sleep,
        )

        with pytest.raises(EmbeddingProviderError) as exc_info:
            service.embed_texts(["Auth failure test"])

        assert exc_info.value.is_transient is False
        assert provider.call_count == 1

    def test_multi_batch_retry_preserves_overall_order(self, noop_sleep):
        """Batch 1 succeeds, batch 2 fails once then succeeds; all results ordered."""
        # 4 texts with batch_size=2 -> 2 batches
        # batch 1: call 1 (succeeds)
        # batch 2: call 2 (fails), call 3 (succeeds)
        provider = FakeEmbeddingProvider(fail_on_calls={2})
        service = EmbeddingService(
            provider=provider,
            batch_size=2,
            max_retries=2,
            sleep_fn=noop_sleep,
        )

        results = service.embed_texts(["T0", "T1", "T2", "T3"])
        assert len(results) == 4
        assert provider.call_count == 3
        assert [r.index for r in results] == [0, 1, 2, 3]

    def test_calculate_delay_exponential_growth(self, fake_provider: FakeEmbeddingProvider, noop_sleep):
        """Delay increases exponentially with attempt number, plus jitter."""
        service = EmbeddingService(
            provider=fake_provider,
            retry_base_delay=1.0,
            sleep_fn=noop_sleep,
        )
        # Attempt 1: 1.0 * 2^0 + jitter [0, 0.5] -> [1.0, 1.5]
        d1 = service._calculate_delay(1)
        assert 1.0 <= d1 <= 1.5

        # Attempt 2: 1.0 * 2^1 + jitter [0, 0.5] -> [2.0, 2.5]
        d2 = service._calculate_delay(2)
        assert 2.0 <= d2 <= 2.5

        # Attempt 3: 1.0 * 2^2 + jitter [0, 0.5] -> [4.0, 4.5]
        d3 = service._calculate_delay(3)
        assert 4.0 <= d3 <= 4.5

    def test_sleep_fn_invoked_with_expected_delays(self):
        """Verifies that sleep_fn receives calculated delay on retry."""
        slept_durations: list[float] = []

        def recording_sleep(delay: float) -> None:
            slept_durations.append(delay)

        provider = FakeEmbeddingProvider(fail_on_calls={1, 2})
        service = EmbeddingService(
            provider=provider,
            max_retries=2,
            retry_base_delay=1.0,
            sleep_fn=recording_sleep,
        )

        service.embed_texts(["Text"])
        assert len(slept_durations) == 2
        # First retry delay in [1.0, 1.5]
        assert 1.0 <= slept_durations[0] <= 1.5
        # Second retry delay in [2.0, 2.5]
        assert 2.0 <= slept_durations[1] <= 2.5


# ======================================================================
# 4. Input Validation Tests
# ======================================================================

class TestEmbeddingValidation:
    """Tests for input sanity and configuration validation."""

    def test_empty_string_in_list_raises_error(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Empty string '' in input list raises EmbeddingValidationError."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            service.embed_texts(["Valid", "", "Also valid"])

        assert "index 1" in str(exc_info.value)
        assert fake_provider.call_count == 0

    def test_whitespace_only_string_raises_error(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Whitespace-only string in input list raises EmbeddingValidationError."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            service.embed_texts(["   \t\n  "])

        assert "index 0" in str(exc_info.value)
        assert fake_provider.call_count == 0

    def test_non_string_element_raises_error(self, service: EmbeddingService, fake_provider: FakeEmbeddingProvider):
        """Non-string item in input list raises EmbeddingValidationError."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            service.embed_texts(["Valid", 12345])  # type: ignore[list-item]

        assert "index 1" in str(exc_info.value)
        assert fake_provider.call_count == 0

    @pytest.mark.parametrize("invalid_batch_size", [0, -1, -10])
    def test_invalid_batch_size_raises_error(self, fake_provider: FakeEmbeddingProvider, invalid_batch_size: int):
        """batch_size <= 0 raises EmbeddingValidationError at construction."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            EmbeddingService(provider=fake_provider, batch_size=invalid_batch_size)
        assert "batch_size must be greater than 0" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_max_tokens", [0, -1, -100])
    def test_invalid_max_tokens_raises_error(self, fake_provider: FakeEmbeddingProvider, invalid_max_tokens: int):
        """max_tokens <= 0 raises EmbeddingValidationError at construction."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            EmbeddingService(provider=fake_provider, max_tokens=invalid_max_tokens)
        assert "max_tokens must be greater than 0" in str(exc_info.value)

    def test_invalid_max_retries_raises_error(self, fake_provider: FakeEmbeddingProvider):
        """max_retries < 0 raises EmbeddingValidationError at construction."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            EmbeddingService(provider=fake_provider, max_retries=-1)
        assert "max_retries must be non-negative" in str(exc_info.value)

    def test_invalid_retry_base_delay_raises_error(self, fake_provider: FakeEmbeddingProvider):
        """retry_base_delay < 0 raises EmbeddingValidationError at construction."""
        with pytest.raises(EmbeddingValidationError) as exc_info:
            EmbeddingService(provider=fake_provider, retry_base_delay=-0.5)
        assert "retry_base_delay must be non-negative" in str(exc_info.value)


# ======================================================================
# 5. Provider Contract Validation Tests
# ======================================================================

class BadLengthProvider(EmbeddingProvider):
    """Provider returning wrong number of embeddings."""
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2]]  # Always returns 1 vector regardless of batch size


class NonListProvider(EmbeddingProvider):
    """Provider returning non-list output."""
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return {"bad": "output"}  # type: ignore[return-value]


class EmptyVectorProvider(EmbeddingProvider):
    """Provider returning an empty vector."""
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


class NonNumericVectorProvider(EmbeddingProvider):
    """Provider returning non-numeric values in vector."""
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [["not", "numbers"] for _ in texts]  # type: ignore[list-item]


class TestProviderContractValidation:
    """Tests that the service enforces structural integrity on provider responses."""

    def test_provider_returns_wrong_count(self, noop_sleep):
        """Service raises permanent error when provider returns vector count != input count."""
        service = EmbeddingService(
            provider=BadLengthProvider(),
            batch_size=5,
            sleep_fn=noop_sleep,
        )
        with pytest.raises(EmbeddingProviderError) as exc_info:
            service.embed_texts(["Text 1", "Text 2"])

        assert exc_info.value.is_transient is False
        assert "result count must equal input count" in str(exc_info.value)

    def test_provider_returns_non_list(self, noop_sleep):
        """Service raises permanent error when provider returns non-list."""
        service = EmbeddingService(
            provider=NonListProvider(),
            batch_size=5,
            sleep_fn=noop_sleep,
        )
        with pytest.raises(EmbeddingProviderError) as exc_info:
            service.embed_texts(["Text 1"])

        assert exc_info.value.is_transient is False
        assert "instead of a list" in str(exc_info.value)

    def test_provider_returns_empty_vector(self, noop_sleep):
        """Service raises permanent error when provider returns an empty vector."""
        service = EmbeddingService(
            provider=EmptyVectorProvider(),
            batch_size=5,
            sleep_fn=noop_sleep,
        )
        with pytest.raises(EmbeddingProviderError) as exc_info:
            service.embed_texts(["Text 1"])

        assert exc_info.value.is_transient is False
        assert "expected a non-empty list[float]" in str(exc_info.value)

    def test_provider_returns_non_numeric_vector(self, noop_sleep):
        """Service raises permanent error when provider returns non-numeric values."""
        service = EmbeddingService(
            provider=NonNumericVectorProvider(),
            batch_size=5,
            sleep_fn=noop_sleep,
        )
        with pytest.raises(EmbeddingProviderError) as exc_info:
            service.embed_texts(["Text 1"])

        assert exc_info.value.is_transient is False
        assert "non-numeric values" in str(exc_info.value)


# ======================================================================
# 6. Token Counters and Factory Tests
# ======================================================================

class TestTokenCountersAndFactory:
    """Tests for token counter implementations and service factory."""

    def test_char_approx_token_counter(self):
        """CharApproxTokenCounter uses ceil(chars / 4)."""
        counter = CharApproxTokenCounter()
        assert counter.count("") == 0
        assert counter.count("a") == 1
        assert counter.count("abcd") == 1
        assert counter.count("abcde") == 2
        assert counter.count("a" * 40) == 10

    def test_make_token_counter_char_fallback(self):
        """make_token_counter(auto=False) returns CharApproxTokenCounter."""
        counter = make_token_counter(auto=False)
        assert isinstance(counter, CharApproxTokenCounter)

    def test_create_embedding_service_factory(self, noop_sleep):
        """create_embedding_service builds a valid EmbeddingService with fallback."""
        service = create_embedding_service(sleep_fn=noop_sleep)
        assert isinstance(service, EmbeddingService)
        # By default in test environment without OPENAI_API_KEY, uses FakeEmbeddingProvider
        assert isinstance(service._provider, FakeEmbeddingProvider)

        # Ensure service works
        results = service.embed_texts(["Test factory"])
        assert len(results) == 1
        assert results[0].index == 0


# ======================================================================
# 7. Data Models Tests
# ======================================================================

class TestEmbeddingModels:
    """Tests for EmbeddingRequest and EmbeddingResult models."""

    def test_embedding_request_frozen(self):
        """EmbeddingRequest is immutable (frozen=True)."""
        req = EmbeddingRequest(text="Hello", index=0)
        assert req.text == "Hello"
        assert req.index == 0

        with pytest.raises(ValidationError):
            req.text = "New text"  # type: ignore[misc]

    def test_embedding_request_empty_text_rejected(self):
        """EmbeddingRequest rejects empty string."""
        with pytest.raises(ValidationError):
            EmbeddingRequest(text="", index=0)

    def test_embedding_result_frozen(self):
        """EmbeddingResult is immutable (frozen=True)."""
        res = EmbeddingResult(index=1, embedding=[0.1, 0.2, 0.3], token_count=5)
        assert res.index == 1
        assert res.embedding == [0.1, 0.2, 0.3]
        assert res.token_count == 5

        with pytest.raises(ValidationError):
            res.index = 2  # type: ignore[misc]
