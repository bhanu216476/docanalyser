"""
Embedding provider abstraction and implementations.

Design:
    EmbeddingProvider (ABC)
        ↓
    embed_batch(texts: list[str]) -> list[list[float]]

Implementations provided:
    FakeEmbeddingProvider   — Deterministic stub for unit testing.
                              Zero dependencies, no network calls.
    OpenAIEmbeddingProvider — Production provider using the openai SDK.
                              Requires OPENAI_API_KEY environment variable
                              and the ``openai`` package.

Extension:
    Add future providers (Cohere, Azure OpenAI, local models, etc.) by
    subclassing ``EmbeddingProvider`` and implementing ``embed_batch()``.
    The batching/retry logic in EmbeddingService is provider-agnostic.

Provider contract:
    - embed_batch() receives a non-empty list of non-empty strings.
    - embed_batch() MUST return a list of float vectors with the
      SAME length as the input list, in the SAME order.
    - Transient failures should raise EmbeddingProviderError(is_transient=True).
    - Permanent failures should raise EmbeddingProviderError(is_transient=False).
    - Providers must NOT perform their own batching; that is the service's job.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.embeddings.exceptions import EmbeddingProviderError

logger = logging.getLogger(__name__)

# Default fake vector dimension (arbitrary for testing)
_FAKE_DIMENSION = 8


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All concrete providers must implement ``embed_batch()``.

    The provider is responsible ONLY for making the API call and
    returning raw vectors.  It does NOT handle:
        - batching into smaller groups
        - token validation
        - retry logic
        - result ordering

    These responsibilities belong to ``EmbeddingService``.
    """

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of text strings.

        Args:
            texts: Non-empty list of non-empty strings to embed.
                   The list has already been validated and token-checked
                   by the service layer.

        Returns:
            List of float vectors with ``len(result) == len(texts)``,
            preserving input order.

        Raises:
            EmbeddingProviderError: On provider-level failures.
                Set ``is_transient=True`` for rate-limit / timeout / 5xx.
                Set ``is_transient=False`` for auth / bad-request errors.
        """
        ...  # pragma: no cover


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic fake provider for unit testing.

    Behaviour:
        - Returns a deterministic vector for each text: a list of floats
          derived from the hash of the text, with a fixed dimension.
        - Tracks call count and all received batches for test assertions.
        - Can be configured to raise exceptions on specific call numbers
          to simulate transient failures.

    This provider never makes network calls and has zero external
    dependencies.  It is the ONLY provider used in automated tests.

    Args:
        dimension: Dimension of the returned vectors (default 8).
        fail_on_calls: Set of 1-based call indices on which to raise a
                       transient ``EmbeddingProviderError``.  For example,
                       ``fail_on_calls={1, 2}`` will fail on the first two
                       calls and succeed on the third.
        permanent_fail_on_calls: Like ``fail_on_calls`` but raises a
                                 non-transient error (simulates auth failure).
    """

    def __init__(
        self,
        dimension: int = _FAKE_DIMENSION,
        fail_on_calls: set[int] | None = None,
        permanent_fail_on_calls: set[int] | None = None,
    ) -> None:
        self._dimension = dimension
        self._fail_on_calls: set[int] = fail_on_calls or set()
        self._permanent_fail_on_calls: set[int] = permanent_fail_on_calls or set()
        self._call_count = 0
        self._received_batches: list[list[str]] = []

    # ------------------------------------------------------------------
    # Test introspection helpers
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Total number of times embed_batch() was called."""
        return self._call_count

    @property
    def received_batches(self) -> list[list[str]]:
        """All batches received, in call order. Useful for assertions."""
        return list(self._received_batches)

    def reset(self) -> None:
        """Reset call count and received batches (useful between test cases)."""
        self._call_count = 0
        self._received_batches = []

    # ------------------------------------------------------------------
    # Provider implementation
    # ------------------------------------------------------------------

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Return a deterministic fake vector for each text.

        The vector is derived from ``hash(text) % 100 / 100.0`` spread
        across all dimensions, making it deterministic within a Python
        process (uses built-in hash, which is consistent per run with
        ``PYTHONHASHSEED`` set, but we ensure determinism by using the
        index as additional input).

        Args:
            texts: Batch of text strings to embed.

        Returns:
            List of float vectors of length ``self._dimension``.

        Raises:
            EmbeddingProviderError: If configured to fail on this call.
        """
        self._call_count += 1
        self._received_batches.append(list(texts))

        if self._call_count in self._permanent_fail_on_calls:
            raise EmbeddingProviderError(
                f"FakeEmbeddingProvider: permanent failure on call {self._call_count}",
                is_transient=False,
            )

        if self._call_count in self._fail_on_calls:
            raise EmbeddingProviderError(
                f"FakeEmbeddingProvider: transient failure on call {self._call_count}",
                is_transient=True,
            )

        return [self._make_vector(text, idx) for idx, text in enumerate(texts)]

    def _make_vector(self, text: str, position: int) -> list[float]:
        """
        Generate a deterministic float vector from a text string.

        Uses a simple formula rather than random() to ensure tests can
        verify exact vector values when needed.
        """
        base = (len(text) * (position + 1)) % 100
        return [round((base + dim) / 100.0, 4) for dim in range(self._dimension)]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Production embedding provider using the OpenAI Embeddings API.

    Requires:
        - ``openai`` package installed: pip install openai
        - ``OPENAI_API_KEY`` environment variable (read via Settings)

    Model:
        Configured via ``Settings.embedding_model``.
        Default: ``text-embedding-3-small``

    Raises:
        ImportError: If the ``openai`` package is not installed.
        EmbeddingProviderError(is_transient=False): On authentication failure.
        EmbeddingProviderError(is_transient=True): On rate limits / timeouts.

    Note:
        This provider does NOT perform its own batching.  The service layer
        controls batch sizes.  Each call to ``embed_batch()`` issues exactly
        one API request.
    """

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAIEmbeddingProvider. "
                "Install it with: pip install openai"
            ) from exc

        if not api_key:
            raise EmbeddingProviderError(
                "OPENAI_API_KEY is not configured. "
                "Set the OPENAI_API_KEY environment variable.",
                is_transient=False,
            )

        self._model = model
        # Create a single client instance — reused across all embed_batch() calls
        self._client = openai.OpenAI(api_key=api_key)
        logger.info(
            "OpenAIEmbeddingProvider initialised: model=%s", model
        )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Call the OpenAI Embeddings API for the given batch of texts.

        Args:
            texts: Batch of validated, token-checked text strings.

        Returns:
            List of float vectors, one per input text, in input order.

        Raises:
            EmbeddingProviderError: Wraps any OpenAI API error with the
                appropriate ``is_transient`` flag.
        """
        try:
            import openai  # noqa: PLC0415

            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            # OpenAI returns embeddings sorted by index — verify and return
            sorted_data = sorted(response.data, key=lambda d: d.index)
            return [item.embedding for item in sorted_data]

        except openai.AuthenticationError as exc:
            raise EmbeddingProviderError(
                f"OpenAI authentication failed: {exc}",
                is_transient=False,
            ) from exc

        except openai.BadRequestError as exc:
            raise EmbeddingProviderError(
                f"OpenAI rejected the request (bad input): {exc}",
                is_transient=False,
            ) from exc

        except (openai.RateLimitError, openai.APITimeoutError) as exc:
            raise EmbeddingProviderError(
                f"OpenAI transient error (rate limit / timeout): {exc}",
                is_transient=True,
            ) from exc

        except openai.APIStatusError as exc:
            # 5xx errors are transient; other status errors are not
            is_transient = exc.status_code is not None and exc.status_code >= 500
            raise EmbeddingProviderError(
                f"OpenAI API error (status {exc.status_code}): {exc}",
                is_transient=is_transient,
            ) from exc

        except Exception as exc:
            # Network-level errors (connection reset, DNS, etc.) are transient
            raise EmbeddingProviderError(
                f"Unexpected error calling OpenAI Embeddings API: {exc}",
                is_transient=True,
            ) from exc
