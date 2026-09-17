"""Provider-independent request and response models for text generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMRequest(BaseModel):
    prompt: str = Field(..., description="Non-empty prompt sent to the provider.")
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    model_config = ConfigDict(frozen=True)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("prompt cannot be empty or whitespace-only")
        return value


class LLMResponse(BaseModel):
    text: str
    model: str = Field(..., min_length=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(frozen=True)