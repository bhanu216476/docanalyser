"""Orchestration for producing answers from structured evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.generation.models import GeneratedAnswer, GenerationRequest
from app.generation.prompt import PromptBuilder

if TYPE_CHECKING:
    from app.llm.client import LLMClient


class AnswerGenerator:
    def __init__(self, client: LLMClient, prompt_builder: PromptBuilder) -> None:
        self._client = client
        self._prompt_builder = prompt_builder

    def generate(self, request: GenerationRequest) -> GeneratedAnswer:
        prompt = self._prompt_builder.build(request.query, request.context)
        response = self._client.generate(prompt)
        return GeneratedAnswer(
            answer=response.text,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )