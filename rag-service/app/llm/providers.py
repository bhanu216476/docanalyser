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
        prompt_text = str(prompt)

        if legacy_version in self._custom_responses:
            text = self._custom_responses[legacy_version]
        else:
            prompt_str = str(prompt)
            if "Evidence Context:\n" in prompt_str or "<context>" in prompt_str:
                context_part = ""
                if "<context>" in prompt_str:
                    context_part = prompt_str.split("<context>", 1)[1].split("</context>", 1)[0].strip()
                elif "Evidence Context:\n" in prompt_str:
                    context_part = (
                        prompt_str.split("Evidence Context:\n", 1)[1]
                        .split("User Question:", 1)[0]
                        .strip()
                    )
                if context_part and len(context_part) > 10:
                    clean_ctx = " ".join(context_part.split()[:80])
                    p_lower = prompt_str.lower()
                    if any(w in p_lower for w in ("question", "quiz", "test", "comprehension")):
                        text = (
                            "Here are 5 questions based on your uploaded document to test comprehension! ✨\n\n"
                            f"1. What is the central subject or objective introduced in this document? [1]\n"
                            f"2. What core roles, criteria, or technical details are specified here? [1]\n"
                            f"3. How does the text describe the operational process or background? [1]\n"
                            f"4. What measurable outcomes, rules, or standards are emphasized? [1]\n"
                            f"5. What are the key conclusions, qualifications, or next steps highlighted? [1]\n\n"
                            "Feel free to try answering any of these, or ask me to explain any question in detail! 😊"
                        )
                    elif any(w in p_lower for w in ("explore", "what is about", "summarize", "overview", "detail", "tell")):
                        text = (
                            f"Here is a helpful overview of what this document is about! ✨\n\n"
                            f"### 📄 Document Summary\n"
                            f"{clean_ctx}... [1]\n\n"
                            f"### 💡 Key Takeaways\n"
                            f"- **Core Focus**: Introduces foundational background and key context. [1]\n"
                            f"- **Primary Information**: Covers essential specifications, roles, and procedures. [1]\n"
                            f"- **Next Steps**: Provides actionable guidelines and supporting details.\n\n"
                            f"Let me know if you would like me to drill into any specific section! 😊"
                        )
                    else:
                        text = (
                            f"Here is what I found in your documents! ✨\n\n"
                            f"{clean_ctx}... [1]\n\n"
                            f"Let me know if you would like me to explain anything in more detail! 😊"
                        )
                else:
                    if legacy_version == "maddy" or "maddy" in prompt_str.lower():
                        text = (
                            "I searched through the uploaded documents, but couldn't find specific details "
                            "addressing that question. Feel free to rephrase or clear the document filter "
                            "if you'd like to ask a general question! 😊"
                        )
                    else:
                        text = (
                            "I couldn't find enough information in the uploaded "
                            "documents to answer this question."
                        )
            elif any(g in prompt_str.lower() for g in ("hi", "hello", "hey", "who are you")):
                text = (
                    "Hello! ✨ I'm Maddy, your friendly AI document assistant and conversational companion. "
                    "You can ask me questions about your uploaded documents, request summaries, or chat about "
                    "any topic you'd like to explore. How can I help you today? 😊"
                )
            else:
                text = f"I'd be happy to help with that! ✨ Here is what I can share regarding your question: {prompt_str[:120]}"

        response = LLMResponse(
            text=text,
            model=model,
            input_tokens=len(prompt_text.split()),
            output_tokens=len(text.split()),
            total_tokens=len(prompt_text.split()) + len(text.split()),
        )
        if legacy_version is not None:
            object.__setattr__(response, "_legacy_version", legacy_version)
        return response


class OpenAILLMProvider(LLMProvider):
    """OpenAI Responses API adapter with no retry orchestration."""

    def __init__(self, api_key: str, *, timeout: float = 60.0) -> None:
        try:
            import openai
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
        prompt: str | object,
        *,
        model: str,
        temperature: float,
        max_output_tokens: int,
        messages: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        chosen_model = model
        if not chosen_model or chosen_model in ("gpt-5.6-luna", "default"):
            chosen_model = "gpt-4o-mini"

        # Build chat messages array
        chat_messages: list[dict[str, str]]
        if messages:
            chat_messages = messages
        elif hasattr(prompt, "messages") and isinstance(prompt.messages, list) and prompt.messages:
            chat_messages = [
                {
                    "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                    "content": m.content,
                }
                for m in prompt.messages
            ]
        else:
            chat_messages = [{"role": "user", "content": str(prompt)}]

        prompt_str = str(prompt)

        try:
            # Prefer standard chat completions API if available on client
            if hasattr(self._client, "chat") and hasattr(self._client.chat, "completions"):
                try:
                    response = self._client.chat.completions.create(
                        model=chosen_model,
                        messages=chat_messages,
                        temperature=temperature,
                        max_tokens=max_output_tokens,
                    )
                    text = response.choices[0].message.content or ""
                    usage = getattr(response, "usage", None)
                    return LLMResponse(
                        text=text,
                        model=str(getattr(response, "model", chosen_model) or chosen_model),
                        input_tokens=_usage_value(usage, "prompt_tokens") or _usage_value(usage, "input_tokens"),
                        output_tokens=_usage_value(usage, "completion_tokens") or _usage_value(usage, "output_tokens"),
                        total_tokens=_usage_value(usage, "total_tokens"),
                    )
                except Exception as chat_err:
                    # If chat.completions failed, fall through to responses.create if available
                    if not (hasattr(self._client, "responses") and hasattr(self._client.responses, "create")):
                        raise chat_err

            response = self._client.responses.create(
                model=chosen_model,
                input=prompt_str,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            usage = getattr(response, "usage", None)
            return LLMResponse(
                text=str(getattr(response, "output_text", "") or ""),
                model=str(getattr(response, "model", chosen_model) or chosen_model),
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

    def generate_stream(
        self,
        prompt: str | object,
        *,
        model: str,
        temperature: float,
        max_output_tokens: int,
        messages: list[dict[str, str]] | None = None,
    ):
        """Yield real-time text chunks using OpenAI chat completion streaming."""
        chosen_model = model
        if not chosen_model or chosen_model in ("gpt-5.6-luna", "default"):
            chosen_model = "gpt-4o-mini"

        if messages:
            chat_messages = messages
        elif hasattr(prompt, "messages") and isinstance(prompt.messages, list) and prompt.messages:
            chat_messages = [
                {
                    "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                    "content": m.content,
                }
                for m in prompt.messages
            ]
        else:
            chat_messages = [{"role": "user", "content": str(prompt)}]

        try:
            stream = self._client.chat.completions.create(
                model=chosen_model,
                messages=chat_messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
                stream=True,
            )
            for chunk in stream:
                content = (
                    chunk.choices[0].delta.content
                    if chunk.choices and hasattr(chunk.choices[0], "delta")
                    else ""
                )
                if content:
                    yield content
        except Exception as exc:
            logger.warning("Streaming failed (%s); returning batch fallback", exc)
            fallback = self.generate(
                prompt,
                model=chosen_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                messages=messages,
            )
            yield fallback.response_text


def _usage_value(usage: Any, name: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
    return int(value) if value is not None else None
