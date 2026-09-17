"""
LLM provider abstraction and fake/mock provider for offline testing.

Defines:
- LLMResponse: typed response from any LLM provider.
- LLMProvider: structural Protocol for provider implementations.
- FakeLLMProvider: deterministic offline provider for unit tests and experiments.

The Protocol-based design ensures future providers (OpenAI, Vertex, Ollama, etc.)
can be swapped in without modifying the Prompt layer. Never couple prompt
experiments to a specific vendor.
"""

from __future__ import annotations

import time
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.llm.prompts.models import Prompt, PromptVersion


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class LLMResponse(BaseModel):
    """
    A response returned by an LLM provider.

    Attributes:
        version: The PromptVersion that generated this response.
        response_text: The model's generated text.
        latency_ms: Wall-clock time from request to response in milliseconds.
        prompt_tokens: Estimated or reported input token count (0 if unavailable).
        model_id: Identifier of the model that produced the response (if known).
    """

    version: PromptVersion = Field(
        ...,
        description="Prompt version that produced this response.",
    )
    response_text: str = Field(
        ...,
        description="Generated response text from the LLM.",
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock latency from prompt submission to response in ms.",
    )
    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Input token count, if reported by the provider.",
    )
    model_id: str = Field(
        default="",
        description="Provider-reported model identifier.",
    )

    model_config = ConfigDict(frozen=True, protected_namespaces=())


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """
    Structural protocol for LLM providers.

    Any class implementing `generate(prompt: Prompt) -> LLMResponse` satisfies
    this protocol. No inheritance required.
    """

    def generate(self, prompt: Prompt) -> LLMResponse:
        """
        Generate a response for the given Prompt.

        Args:
            prompt: Fully assembled Prompt from the PromptBuilder.

        Returns:
            LLMResponse with the generated text and latency.
        """
        ...


# ---------------------------------------------------------------------------
# Fake provider for offline tests and experiments
# ---------------------------------------------------------------------------


class FakeLLMProvider:
    """
    Deterministic offline LLM provider for unit tests and CI.

    Never calls any external API. Generates reproducible responses based on
    the prompt version and the citation IDs present in the prompt, making it
    suitable for verifying prompt structure, experiment runner logic, and
    evaluation record integrity.

    Args:
        simulated_delay_ms: Optional artificial latency to add in milliseconds.
                            Useful for testing latency measurement code.
        custom_responses: Optional mapping of PromptVersion → response text.
                          Overrides the default template responses.
    """

    _DEFAULT_TEMPLATES: dict[PromptVersion, str] = {
        PromptVersion.V1: (
            "Based on the provided context, {summary}. "
            "This information is sourced from the supplied documents."
        ),
        PromptVersion.V2: (
            "Based on the provided context: {summary} {citations}. "
            "Only the supplied sources were used to produce this answer."
        ),
        PromptVersion.V3: (
            "Grounded answer: {summary} {citations}. "
            "This answer is limited to what the supplied context states."
        ),
    }

    def __init__(
        self,
        simulated_delay_ms: float = 0.0,
        custom_responses: Optional[dict[PromptVersion, str]] = None,
    ) -> None:
        self._delay_ms = max(0.0, simulated_delay_ms)
        self._custom: dict[PromptVersion, str] = custom_responses or {}

    def generate(self, prompt: Prompt) -> LLMResponse:
        """
        Produce a deterministic offline response.

        The response text:
        1. Summarises the first 60 characters of context_text.
        2. Appends any citation IDs present in the prompt.
        3. Uses the version-specific response template.

        This never calls an external service and is safe for CI environments
        with no API credentials.
        """
        t_start = time.perf_counter()

        if self._delay_ms > 0:
            time.sleep(self._delay_ms / 1000.0)

        response_text = self._render(prompt)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        return LLMResponse(
            version=prompt.version,
            response_text=response_text,
            latency_ms=latency_ms,
            prompt_tokens=sum(
                len(m.content.split()) for m in prompt.messages
            ),
            model_id="fake-llm-provider",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _render(self, prompt: Prompt) -> str:
        """Render a deterministic response for the given prompt."""
        if prompt.version in self._custom:
            return self._custom[prompt.version]

        template = self._DEFAULT_TEMPLATES.get(
            prompt.version,
            "Response based on supplied context. {summary} {citations}",
        )

        # Safe summary: first 60 chars of context_text, or fallback
        raw_ctx = prompt.context_text.strip()
        if raw_ctx:
            summary = raw_ctx[:60].replace("\n", " ").strip()
            if len(raw_ctx) > 60:
                summary += "..."
        else:
            summary = "the provided sources do not contain sufficient information"

        # Format citation IDs if present
        if prompt.citation_ids:
            citations = " ".join(prompt.citation_ids)
        else:
            citations = ""

        return template.format(summary=summary, citations=citations).strip()
