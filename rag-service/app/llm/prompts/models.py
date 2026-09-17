"""
Prompt data models for the LLM layer.

Defines:
- PromptVersion: versioned prompt identifier enum.
- MessageRole: standard LLM message roles (system, user).
- PromptMessage: a single role-content pair in a messages list.
- Prompt: fully assembled, immutable prompt ready for LLM injection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PromptVersion(str, Enum):
    """
    Versioned prompt identifiers.

    Each version is a distinct, reproducible prompt design.
    Changing wording materially requires a new version — do not silently
    modify an existing version after experiments have been recorded.
    """

    V1 = "v1"
    V2 = "v2"
    V3 = "v3"

    @classmethod
    def from_string(cls, value: str) -> "PromptVersion":
        """
        Parse a version string (case-insensitive) to a PromptVersion.

        Args:
            value: Version string such as 'v1', 'V2', 'v3'.

        Returns:
            Matching PromptVersion member.

        Raises:
            ValueError: If the string does not match any known version.
        """
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        valid = ", ".join(m.value for m in cls)
        raise ValueError(
            f"Unknown prompt version '{value}'. Valid versions: {valid}."
        )


class MessageRole(str, Enum):
    """Standard LLM message roles."""

    SYSTEM = "system"
    USER = "user"


class PromptMessage(BaseModel):
    """
    A single message in the LLM messages array.

    Attributes:
        role: The message sender role ('system' or 'user').
        content: The raw text content of the message.
    """

    role: MessageRole = Field(..., description="Message sender role.")
    content: str = Field(..., description="Message text content.")

    model_config = ConfigDict(frozen=True)


class Prompt(BaseModel):
    """
    A fully assembled, version-tagged prompt ready for LLM injection.

    Attributes:
        version: The PromptVersion that generated this prompt.
        system_prompt: The system instruction text.
        context_text: The formatted evidence context from the Context Builder.
        query: The original user question, unchanged.
        messages: Ordered list of PromptMessage objects for the LLM API.
        citation_ids: Citation IDs present in the context (e.g. ['[1]', '[2]']).
        built_at: UTC timestamp of when the prompt was assembled.
    """

    version: PromptVersion = Field(
        ...,
        description="Prompt version used to build this prompt.",
    )
    system_prompt: str = Field(
        ...,
        description="System instruction text defining assistant behavior.",
    )
    context_text: str = Field(
        ...,
        description="Formatted evidence context from the Context Builder (unmodified).",
    )
    query: str = Field(
        ...,
        description="User question — inserted separately from context.",
    )
    messages: list[PromptMessage] = Field(
        ...,
        description="Ordered messages for the LLM API (system then user).",
    )
    citation_ids: list[str] = Field(
        default_factory=list,
        description="Citation IDs present in the context, e.g. ['[1]', '[2]'].",
    )
    built_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of prompt assembly.",
    )

    model_config = ConfigDict(frozen=True)

    @property
    def has_context(self) -> bool:
        """True if the prompt contains non-empty context evidence."""
        return bool(self.context_text.strip())

    @property
    def citation_count(self) -> int:
        """Number of citation IDs present in this prompt."""
        return len(self.citation_ids)
