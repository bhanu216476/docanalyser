"""LLM provider adapters and provider-independent response normalization."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.llm.exceptions import LLMProviderError
from app.llm.models import LLMResponse
from app.llm.prompts.models import PromptVersion

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMResponse:
        """Generate one response for an already validated prompt."""
        ...


class FakeLLMProvider(LLMProvider):
    """Deterministic, network-free provider for development and tests."""

    def __init__(
        self,
        fail_on_calls: set[int] | None = None,
        permanent_fail_on_calls: set[int] | None = None,
        custom_responses: dict[PromptVersion, str] | None = None,
    ) -> None:
        self._fail_on_calls = fail_on_calls or set()
        self._permanent_fail_on_calls = permanent_fail_on_calls or set()
        self._custom_responses = custom_responses or {}
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(
        self,
        prompt: str | object,
        *,
        model: str = "fake-model",
        temperature: float = 0.0,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        self._call_count += 1
        if self._call_count in self._permanent_fail_on_calls:
            raise LLMProviderError("Fake LLM permanent failure", is_transient=False)
        if self._call_count in self._fail_on_calls:
            raise LLMProviderError("Fake LLM transient failure", is_transient=True)
        legacy_version = getattr(prompt, "version", None)
        if legacy_version in self._custom_responses:
            text = self._custom_responses[legacy_version]
        else:
            text = f"FAKE_RESPONSE[{prompt}]"
        response = LLMResponse(
            text=text,
            model=model,
            input_tokens=len(str(prompt).split()),
            output_tokens=len(text.split()),
            total_tokens=len(str(prompt).split()) + len(text.split()),
        )
        if legacy_version is not None:
            object.__setattr__(response, "_legacy_version", legacy_version)
        return response


class OpenAILLMProvider(LLMProvider):
    """OpenAI Responses API adapter with no retry orchestration."""

    def __init__(self, api_key: str, *, timeout: float = 60.0) -> None:
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAILLMProvider. "
                "Install it with: pip install openai"
            ) from exc
        if not api_key:
            raise LLMProviderError(
                "OPENAI_API_KEY is not configured", is_transient=False
            )
        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        logger.info("OpenAILLMProvider initialised")

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMResponse:
        try:
            response = self._client.responses.create(
                model=model,
                input=prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            usage = getattr(response, "usage", None)
            return LLMResponse(
                text=str(getattr(response, "output_text", "") or ""),
                model=str(getattr(response, "model", model) or model),
                input_tokens=_usage_value(usage, "input_tokens"),
                output_tokens=_usage_value(usage, "output_tokens"),
                total_tokens=_usage_value(usage, "total_tokens"),
            )
        except self._openai.AuthenticationError as exc:
            raise LLMProviderError(
                "OpenAI authentication failed", is_transient=False
            ) from exc
        except self._openai.PermissionDeniedError as exc:
            raise LLMProviderError(
                "OpenAI permission denied", is_transient=False
            ) from exc
        except self._openai.BadRequestError as exc:
            raise LLMProviderError(
                "OpenAI rejected the generation request", is_transient=False
            ) from exc
        except self._openai.NotFoundError as exc:
            raise LLMProviderError(
                "OpenAI model or resource was not found", is_transient=False
            ) from exc
        except (self._openai.RateLimitError, self._openai.APITimeoutError) as exc:
            raise LLMProviderError(
                "OpenAI rate limit or timeout", is_transient=True
            ) from exc
        except self._openai.APIConnectionError as exc:
            raise LLMProviderError(
                "OpenAI connection failed", is_transient=True
            ) from exc
        except self._openai.APIStatusError as exc:
            transient = exc.status_code is not None and exc.status_code >= 500
            raise LLMProviderError(
                f"OpenAI API error (status {exc.status_code})",
                is_transient=transient,
            ) from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                "Unexpected OpenAI generation failure", is_transient=True
            ) from exc


def _usage_value(usage: Any, name: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
    return int(value) if value is not None else None