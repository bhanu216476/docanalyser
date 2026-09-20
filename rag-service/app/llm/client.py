"""LLM orchestration: validation, token limits, retries, and factory setup."""

from __future__ import annotations

from collections.abc import Callable
import logging
import random
import time

from app.embeddings.token_counter import TokenCounter, make_token_counter
from app.llm.exceptions import (
    LLMProviderError,
    LLMRetryExhaustedError,
    LLMTokenLimitError,
    LLMValidationError,
)
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers import FakeLLMProvider, LLMProvider, OpenAILLMProvider

logger = logging.getLogger(__name__)
_JITTER_MAX = 0.5


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        model: str,
        max_input_tokens: int,
        max_output_tokens: int,
        temperature: float,
        timeout: float,
        max_retries: int,
        retry_base_delay: float,
        token_counter: TokenCounter | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if not model.strip():
            raise LLMValidationError("model must not be empty")
        if max_input_tokens <= 0 or max_output_tokens <= 0:
            raise LLMValidationError("token limits must be greater than 0")
        if not 0.0 <= temperature <= 2.0:
            raise LLMValidationError("temperature must be between 0.0 and 2.0")
        if timeout <= 0:
            raise LLMValidationError("timeout must be greater than 0")
        if max_retries < 0:
            raise LLMValidationError("max_retries must be non-negative")
        if retry_base_delay < 0:
            raise LLMValidationError("retry_base_delay must be non-negative")

        self._provider = provider
        self._model = model.strip()
        self._max_input_tokens = max_input_tokens
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._token_counter = token_counter or make_token_counter(model=self._model)
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep

    def generate(
        self,
        prompt: str,
        *,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        try:
            request = LLMRequest(
                prompt=prompt,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        except ValueError as exc:
            raise LLMValidationError(str(exc)) from exc

        if (
            request.max_output_tokens is not None
            and request.max_output_tokens > self._max_output_tokens
        ):
            raise LLMValidationError(
                "max_output_tokens override cannot exceed the configured maximum"
            )

        prompt_tokens = self._token_counter.count(request.prompt)
        if prompt_tokens > self._max_input_tokens:
            raise LLMTokenLimitError(prompt_tokens, self._max_input_tokens)

        output_limit = (
            request.max_output_tokens
            if request.max_output_tokens is not None
            else self._max_output_tokens
        )
        sampling_temperature = (
            request.temperature
            if request.temperature is not None
            else self._temperature
        )

        for attempt in range(1, self._max_retries + 2):
            try:
                return self._provider.generate(
                    request.prompt,
                    model=self._model,
                    temperature=sampling_temperature,
                    max_output_tokens=output_limit,
                )
            except LLMProviderError as exc:
                if not exc.is_transient:
                    raise
                if attempt > self._max_retries:
                    raise LLMRetryExhaustedError(attempt, exc) from exc
                delay = self._retry_base_delay * (2 ** (attempt - 1))
                delay += random.uniform(0, _JITTER_MAX)
                logger.warning(
                    "Transient LLM provider error: attempt=%d max_retries=%d "
                    "delay=%.3f error_type=%s",
                    attempt,
                    self._max_retries,
                    delay,
                    type(exc).__name__,
                )
                self._sleep(delay)

        raise AssertionError("unreachable")


def create_llm_client(
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> LLMClient:
    from app.core.config import settings

    if settings.openai_api_key:
        try:
            provider: LLMProvider = OpenAILLMProvider(
                settings.openai_api_key,
                timeout=settings.llm_timeout,
            )
        except ImportError:
            logger.warning(
                "openai package is unavailable; using FakeLLMProvider for development"
            )
            provider = FakeLLMProvider()
    else:
        logger.warning(
            "OPENAI_API_KEY is not set; using FakeLLMProvider for development only"
        )
        provider = FakeLLMProvider()

    return LLMClient(
        provider=provider,
        model=settings.llm_model,
        max_input_tokens=settings.llm_max_input_tokens,
        max_output_tokens=settings.llm_max_output_tokens,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        retry_base_delay=settings.llm_retry_base_delay,
        token_counter=make_token_counter(model=settings.llm_model),
        sleep_fn=sleep_fn,
    )