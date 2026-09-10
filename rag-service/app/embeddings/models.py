"""
Input and output data models for the embedding service.

Pipeline position:
    Chunk/Text
        ↓
    EmbeddingRequest    ← validated input unit
        ↓
    EmbeddingService
        ↓
    EmbeddingResult     ← output unit preserving original index

Design decisions:
    - ``EmbeddingRequest`` wraps a single text string with its original
      positional index so that ordering guarantees can be maintained
      even when batches are processed out of sequence or retried.

    - ``EmbeddingResult`` carries the same ``index`` field, enabling
      the service to sort results back into input order after all
      batches complete.

    - Both models are frozen (immutable) consistent with the rest of
      the DocAnalyser Pydantic model conventions.

    - The service also accepts ``Chunk`` objects directly via the
      ``EmbeddingService.embed_chunks()`` helper, which converts them
      to ``EmbeddingRequest`` objects internally.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmbeddingRequest(BaseModel):
    """
    A single validated embedding input unit.

    Attributes:
        text:  The text to embed. Must be non-empty and non-whitespace.
               Validated before any provider interaction.
        index: The 0-based position of this text in the original caller's
               input list. Preserved through batching and retries so that
               results can be returned in the original order.
    """

    text: str = Field(
        ...,
        description="Non-empty text to embed.",
    )
    index: int = Field(
        ...,
        ge=0,
        description="0-based position of this text in the original input sequence.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("text")
    @classmethod
    def validate_text_non_empty(cls, v: str) -> str:
        """Reject empty or whitespace-only text before any provider call."""
        if not v or not v.strip():
            raise ValueError(
                "EmbeddingRequest text cannot be empty or whitespace-only. "
                "Validate chunk content before creating embedding requests."
            )
        return v


class EmbeddingResult(BaseModel):
    """
    A single embedding output unit returned by the embedding service.

    Attributes:
        index:       The 0-based position matching the original
                     ``EmbeddingRequest.index``. The service guarantees
                     that results are returned sorted by this field.
        embedding:   The dense float vector produced by the provider.
                     Dimension depends on the configured model.
        token_count: Estimated or measured token count for the input text,
                     useful for monitoring and cost tracking.
    """

    index: int = Field(
        ...,
        ge=0,
        description="0-based position matching the original input index.",
    )
    embedding: Annotated[
        list[float],
        Field(min_length=1, description="Dense embedding vector (non-empty list of floats)."),
    ]
    token_count: int = Field(
        ...,
        ge=0,
        description="Estimated or measured token count for this input.",
    )

    model_config = ConfigDict(frozen=True)
