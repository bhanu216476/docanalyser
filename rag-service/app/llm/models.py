"""Provider-independent request and response models for text generation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import PrivateAttr


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

    _legacy_version: object = PrivateAttr(default=None)

    def __init__(self, **data: Any) -> None:
        legacy_version = data.pop("version", None)
        data.setdefault("text", data.pop("response_text", None))
        data.setdefault("model", data.pop("model_id", None))
        data.setdefault("input_tokens", data.pop("prompt_tokens", None))
        data.pop("latency_ms", None)
        super().__init__(**data)
        if legacy_version is not None:
            object.__setattr__(self, "_legacy_version", legacy_version)

    @property
    def response_text(self) -> str:
        """Compatibility alias for the former demo response field."""
        return self.text

    @property
    def prompt_tokens(self) -> int:
        """Compatibility alias for input token counts."""
        return self.input_tokens or 0

    @property
    def model_id(self) -> str:
        """Compatibility alias for the provider model identifier."""
        return self.model

    @property
    def latency_ms(self) -> float:
        """Compatibility value for legacy offline provider callers."""
        return 0.0

    @property
    def version(self) -> object:
        """Compatibility value populated by the legacy fake-provider path."""
        return self._legacy_version

    model_config = ConfigDict(frozen=True)