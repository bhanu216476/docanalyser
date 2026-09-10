"""
Embedding Service — core batching, validation, retry, and orchestration.

Pipeline position:
    Document
        ↓
    Chunking
        ↓
    EmbeddingService    ← this module
        ↓
    EmbeddingResult[]
        ↓
    Future: Qdrant vector store

Responsibilities of this service:
    ✓ Accept text strings or Chunk objects
    ✓ Validate inputs (empty, whitespace)
    ✓ Enforce per-text token limits before any provider call
    ✓ Batch requests into configurable groups
    ✓ Call the embedding provider once per batch
    ✓ Validate provider responses (count, structure)
    ✓ Retry transient provider failures with exponential backoff + jitter
    ✓ Preserve original input order across batches and retries
    ✓ Return a well-typed list of EmbeddingResult in input order

NOT responsible for:
    ✗ Storing vectors
    ✗ Searching vectors
    ✗ Ranking documents
    ✗ Generating answers

Usage example::

    from app.embeddings import EmbeddingService
    from app.embeddings.providers import FakeEmbeddingProvider

    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider=provider)

    results = service.embed_texts(["Hello world", "Another sentence"])
    # results[0].index == 0, results[1].index == 1

    # Or from Chunk objects:
    chunks = chunker.chunk(document)
    results = service.embed_chunks(chunks)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
import math
import random
import time

from app.embeddings.exceptions import (
    EmbeddingProviderError,
    EmbeddingRetryExhaustedError,
    EmbeddingTokenLimitError,
    EmbeddingValidationError,
)
from app.embeddings.models import EmbeddingRequest, EmbeddingResult
from app.embeddings.providers import EmbeddingProvider
from app.embeddings.token_counter import TokenCounter, make_token_counter
from app.ingestion.chunking.models import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default number of texts to send per provider API call.
DEFAULT_BATCH_SIZE: int = 20

#: Default per-text token limit (matches text-embedding-3-small).
DEFAULT_MAX_TOKENS: int = 8191

#: Default maximum retry attempts for transient failures.
DEFAULT_MAX_RETRIES: int = 3

#: Default base delay (seconds) for exponential backoff.
DEFAULT_RETRY_BASE_DELAY: float = 1.0

#: Maximum jitter added to each retry delay (seconds).
_JITTER_MAX: float = 0.5


class EmbeddingService:
    """
    Production-grade embedding service with batching, validation, and retry.

    The service decouples the orchestration concerns (batching, validation,
    retry) from the provider concern (making the actual API call).  Swapping
    providers requires no change to this class.

    Args:
        provider:        The embedding provider to call.
        batch_size:      Maximum number of texts per provider call. Must be > 0.
        max_tokens:      Maximum tokens allowed per single text input.
                         Must match the configured embedding model's limit.
        max_retries:     Maximum retry attempts for transient failures.
                         0 means no retries.
        retry_base_delay: Base delay (seconds) for exponential backoff.
        token_counter:   Custom token counter.  If None, the best available
                         counter is selected automatically (tiktoken if installed,
                         otherwise character approximation).
        sleep_fn:        Callable used to pause between retries.  Defaults to
                         ``time.sleep``.  Pass a no-op for fast unit tests:
                         ``sleep_fn=lambda _: None``.

    Raises:
        EmbeddingValidationError: If ``batch_size <= 0``, ``max_tokens <= 0``,
                                  or ``max_retries < 0``.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        token_counter: TokenCounter | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        # Validate configuration eagerly so misconfiguration is caught at
        # construction time rather than silently at runtime.
        if batch_size <= 0:
            raise EmbeddingValidationError(
                f"batch_size must be greater than 0, got {batch_size}"
            )
        if max_tokens <= 0:
            raise EmbeddingValidationError(
                f"max_tokens must be greater than 0, got {max_tokens}"
            )
        if max_retries < 0:
            raise EmbeddingValidationError(
                f"max_retries must be non-negative, got {max_retries}"
            )
        if retry_base_delay < 0:
            raise EmbeddingValidationError(
                f"retry_base_delay must be non-negative, got {retry_base_delay}"
            )

        self._provider = provider
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._token_counter: TokenCounter = token_counter or make_token_counter()
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep

        logger.info(
            "EmbeddingService initialised: batch_size=%d max_tokens=%d "
            "max_retries=%d retry_base_delay=%.2f provider=%s",
            self._batch_size,
            self._max_tokens,
            self._max_retries,
            self._retry_base_delay,
            type(self._provider).__name__,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingResult]:
        """
        Generate embeddings for a sequence of text strings.

        Behaviour:
            - Empty input list returns ``[]`` immediately (no provider call).
            - Each text is validated and token-checked before batching.
            - Texts are processed in batches of ``batch_size``.
            - Results are returned in the same order as ``texts``.
            - A failure in any batch raises immediately; partial results are
              NOT returned silently.

        Args:
            texts: Sequence of text strings to embed.  May be empty.

        Returns:
            List of ``EmbeddingResult`` objects in input order.

        Raises:
            EmbeddingValidationError:    If any text is empty or whitespace-only.
            EmbeddingTokenLimitError:    If any text exceeds the token limit.
            EmbeddingProviderError:      If the provider raises a permanent error.
            EmbeddingRetryExhaustedError: If all retries are exhausted on a batch.
        """
        if not texts:
            logger.debug("embed_texts: empty input — returning [] without provider call")
            return []

        # Build and validate EmbeddingRequest objects
        requests = self._build_and_validate_requests(list(texts))

        # Process all batches and collect results
        results = self._process_all_batches(requests)

        # Sort by original index to guarantee input order preservation
        results.sort(key=lambda r: r.index)

        logger.info(
            "embed_texts: completed %d embeddings across %d batch(es)",
            len(results),
            math.ceil(len(requests) / self._batch_size),
        )
        return results

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[EmbeddingResult]:
        """
        Generate embeddings for a sequence of ``Chunk`` objects.

        Convenience wrapper around ``embed_texts()`` that extracts
        the ``content`` field from each chunk.

        Args:
            chunks: Sequence of ``Chunk`` instances from the chunking stage.

        Returns:
            List of ``EmbeddingResult`` objects in input order (matching
            the chunk list position, not ``chunk_index``).

        Raises:
            Same as ``embed_texts()``.
        """
        if not chunks:
            logger.debug("embed_chunks: empty input — returning []")
            return []

        texts = [chunk.content for chunk in chunks]
        return self.embed_texts(texts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_and_validate_requests(
        self,
        texts: list[str],
    ) -> list[EmbeddingRequest]:
        """
        Convert and validate raw text strings into EmbeddingRequest objects.

        Performs two checks per text:
            1. Non-empty, non-whitespace (raises EmbeddingValidationError)
            2. Token count within limit (raises EmbeddingTokenLimitError)

        All checks run upfront before any provider call is made.  This
        means a token-limit violation in chunk 99 of 100 is caught before
        any API cost is incurred.

        Args:
            texts: Raw text strings (list length guaranteed >= 1).

        Returns:
            List of validated EmbeddingRequest objects.
        """
        requests: list[EmbeddingRequest] = []

        for idx, text in enumerate(texts):
            # 1. Validate non-empty string
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingValidationError(
                    f"Text at index {idx} is empty, whitespace-only, or not a string. "
                    f"Remove or filter invalid chunks before embedding."
                )

            # 2. Token limit check
            token_count = self._token_counter.count(text)
            if token_count > self._max_tokens:
                raise EmbeddingTokenLimitError(
                    chunk_index=idx,
                    token_count=token_count,
                    max_tokens=self._max_tokens,
                )

            requests.append(EmbeddingRequest(text=text, index=idx))

        return requests

    def _process_all_batches(
        self,
        requests: list[EmbeddingRequest],
    ) -> list[EmbeddingResult]:
        """
        Split requests into batches and call the provider for each batch.

        Failure in any batch raises immediately.  Results from already-
        completed batches are NOT returned as a partial success.

        Args:
            requests: Fully validated EmbeddingRequest objects.

        Returns:
            Flat list of EmbeddingResult objects (may be in batch order,
            not necessarily input order — caller must sort by index).
        """
        all_results: list[EmbeddingResult] = []
        total_batches = math.ceil(len(requests) / self._batch_size)

        for batch_idx in range(total_batches):
            batch_start = batch_idx * self._batch_size
            batch_end = batch_start + self._batch_size
            batch = requests[batch_start:batch_end]

            logger.debug(
                "Processing batch %d/%d: size=%d",
                batch_idx + 1,
                total_batches,
                len(batch),
            )

            batch_results = self._embed_batch_with_retry(batch, batch_idx)
            all_results.extend(batch_results)

        return all_results

    def _embed_batch_with_retry(
        self,
        batch: list[EmbeddingRequest],
        batch_idx: int,
    ) -> list[EmbeddingResult]:
        """
        Attempt to embed a single batch, retrying on transient failures.

        Retry policy:
            - Only ``EmbeddingProviderError(is_transient=True)`` triggers retry.
            - All other exceptions propagate immediately without retry.
            - Delay between attempts: base_delay * 2^attempt + jitter.
            - Maximum attempts: max_retries + 1 (1 original + max_retries retries).

        Args:
            batch:     Validated requests for this batch.
            batch_idx: 0-based batch index (for logging and error context).

        Returns:
            List of EmbeddingResult with correct index values.

        Raises:
            EmbeddingRetryExhaustedError: If all attempts fail with transient errors.
            EmbeddingProviderError:       If the provider raises a permanent error.
        """
        texts = [req.text for req in batch]
        max_attempts = self._max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            if attempt > 0:
                actual_delay = self._calculate_delay(attempt)
                logger.warning(
                    "Batch %d: retry attempt %d/%d after %.2fs delay. "
                    "Last error: %s",
                    batch_idx,
                    attempt,
                    self._max_retries,
                    actual_delay,
                    last_exc,
                )
                self._sleep(actual_delay)

            try:
                raw_embeddings = self._provider.embed_batch(texts)
                self._validate_provider_response(raw_embeddings, batch, batch_idx)

                # Build EmbeddingResult objects preserving original indices
                results: list[EmbeddingResult] = []
                for req, vector in zip(batch, raw_embeddings):
                    token_count = self._token_counter.count(req.text)
                    results.append(
                        EmbeddingResult(
                            index=req.index,
                            embedding=vector,
                            token_count=token_count,
                        )
                    )

                logger.debug(
                    "Batch %d: completed successfully on attempt %d. "
                    "Embeddings returned: %d",
                    batch_idx,
                    attempt + 1,
                    len(results),
                )
                return results

            except EmbeddingProviderError as exc:
                if not exc.is_transient:
                    # Permanent failure — do not retry
                    logger.error(
                        "Batch %d: permanent provider error on attempt %d: %s",
                        batch_idx,
                        attempt + 1,
                        exc,
                    )
                    raise

                last_exc = exc
                logger.warning(
                    "Batch %d: transient provider error on attempt %d/%d: %s",
                    batch_idx,
                    attempt + 1,
                    max_attempts,
                    exc,
                )

        # All attempts exhausted
        raise EmbeddingRetryExhaustedError(
            attempts=max_attempts,
            batch_index=batch_idx,
            cause=last_exc or RuntimeError("Unknown error"),
        )

    def _validate_provider_response(
        self,
        raw_embeddings: list[list[float]],
        batch: list[EmbeddingRequest],
        batch_idx: int,
    ) -> None:
        """
        Validate the provider's response before trusting it.

        Checks:
            1. Return type is a list.
            2. Length matches the number of inputs.
            3. Each embedding is a non-empty list of floats.

        Args:
            raw_embeddings: Raw return value from provider.embed_batch().
            batch:          The batch of requests that was sent.
            batch_idx:      0-based batch index for error context.

        Raises:
            EmbeddingProviderError(is_transient=False): On any structural mismatch.
        """
        if not isinstance(raw_embeddings, list):
            raise EmbeddingProviderError(
                f"Batch {batch_idx}: provider returned {type(raw_embeddings).__name__} "
                f"instead of a list. Provider contract violation.",
                is_transient=False,
            )

        if len(raw_embeddings) != len(batch):
            raise EmbeddingProviderError(
                f"Batch {batch_idx}: provider returned {len(raw_embeddings)} embedding(s) "
                f"but {len(batch)} were requested. "
                f"Provider contract violation — result count must equal input count.",
                is_transient=False,
            )

        for vec_idx, vector in enumerate(raw_embeddings):
            if not isinstance(vector, list) or not vector:
                raise EmbeddingProviderError(
                    f"Batch {batch_idx}, embedding {vec_idx}: expected a non-empty "
                    f"list[float], got {type(vector).__name__!r}. "
                    f"Provider contract violation.",
                    is_transient=False,
                )
            if not all(isinstance(v, (int, float)) for v in vector):
                raise EmbeddingProviderError(
                    f"Batch {batch_idx}, embedding {vec_idx}: embedding contains "
                    f"non-numeric values. Provider contract violation.",
                    is_transient=False,
                )

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate backoff delay with jitter for a retry attempt.

        Formula: base_delay * 2^(attempt - 1) + uniform(0, _JITTER_MAX)

        Args:
            attempt: 1-based retry attempt (1 for first retry).

        Returns:
            Delay in seconds (float).
        """
        delay = self._retry_base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0, _JITTER_MAX)
        return delay + jitter


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def create_embedding_service(
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> EmbeddingService:
    """
    Convenience factory that creates an ``EmbeddingService`` using the
    application's ``Settings`` configuration.

    Automatically selects the provider based on available credentials:
        - If ``OPENAI_API_KEY`` is configured → ``OpenAIEmbeddingProvider``
        - Otherwise → ``FakeEmbeddingProvider`` (suitable for development only)

    Args:
        sleep_fn: Optional override for the retry sleep function.
                  Pass ``lambda _: None`` for zero-delay tests.

    Returns:
        A fully configured ``EmbeddingService`` instance.

    Warns:
        If no real provider can be instantiated (missing API key / SDK),
        a warning is logged and ``FakeEmbeddingProvider`` is used.
    """
    from app.core.config import settings
    from app.embeddings.providers import FakeEmbeddingProvider, OpenAIEmbeddingProvider

    provider: EmbeddingProvider

    if settings.openai_api_key:
        try:
            provider = OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
            )
        except ImportError:
            logger.warning(
                "openai package not installed — falling back to FakeEmbeddingProvider. "
                "Install openai for production: pip install openai"
            )
            provider = FakeEmbeddingProvider()
    else:
        logger.warning(
            "OPENAI_API_KEY is not set — using FakeEmbeddingProvider. "
            "Set OPENAI_API_KEY in your environment for production use."
        )
        provider = FakeEmbeddingProvider()

    counter = make_token_counter(model=settings.embedding_model)

    return EmbeddingService(
        provider=provider,
        batch_size=settings.embedding_batch_size,
        max_tokens=settings.embedding_max_tokens,
        max_retries=settings.embedding_max_retries,
        retry_base_delay=settings.embedding_retry_base_delay,
        token_counter=counter,
        sleep_fn=sleep_fn,
    )
