"""
Models for the RAG V0.1 end-to-end pipeline.

Defines:
- IngestionResponse: outcome of document ingestion, chunking, and indexing.
- RAGQueryRequest: incoming query and retrieval parameters.
- RAGResponse: end-to-end grounded answer, citations, and stage metrics.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.confidence.models import ConfidenceResult
from app.context.models import Citation
from app.retrieval.models import RetrievalFilter
from app.verification.models import VerificationResult


class IngestionResponse(BaseModel):
    """
    Response returned after a document has been loaded, chunked, embedded, and indexed.
    """

    document_id: str = Field(
        ...,
        description="Deterministic document identifier.",
    )
    file_name: str = Field(
        ...,
        description="Name of the ingested file.",
    )
    file_type: str = Field(
        ...,
        description="Extension/type of the ingested document.",
    )
    chunk_count: int = Field(
        ...,
        ge=0,
        description="Number of chunks extracted and indexed.",
    )
    latency_breakdown_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Monotonic latency in milliseconds for each ingestion stage.",
    )

    model_config = ConfigDict(frozen=True)


class RAGQueryRequest(BaseModel):
    """
    Query request for the RAG pipeline.
    """

    query: str = Field(
        ...,
        min_length=1,
        description="User question string.",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Override final top-k candidates for reranking/context.",
    )
    prompt_version: Optional[str] = Field(
        default=None,
        description="Prompt version override ('v1', 'v2', 'v3').",
    )
    filters: Optional[RetrievalFilter] = Field(
        default=None,
        description="Optional metadata filters for dense and BM25 retrievers.",
    )

    model_config = ConfigDict(frozen=True)


class RAGResponse(BaseModel):
    """
    End-to-end RAG response model.

    Attributes:
        query: Original user question.
        answer: Generated grounded response from LLM.
        citations: List of structured Citation objects used as evidence.
        prompt_version: Prompt version used for generation.
        latency_breakdown_ms: Wall-clock latencies across pipeline stages.
        metadata: Stage counts, token usage, and diagnostic information.
    """

    query: str = Field(
        ...,
        description="User question.",
    )
    answer: str = Field(
        ...,
        description="Grounded response text from the LLM.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Verified citations corresponding to context evidence.",
    )
    prompt_version: str = Field(
        ...,
        description="Prompt version that produced the generation.",
    )
    latency_breakdown_ms: dict[str, float] = Field(
        default_factory=dict,
        description="High-resolution stage latency breakdown in milliseconds.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline metrics and diagnostics (chunk counts, tokens, model info).",
    )
    verification: Optional[VerificationResult] = Field(
        default=None,
        description="Citation verification results if verification was executed.",
    )
    confidence: Optional[ConfidenceResult] = Field(
        default=None,
        description="Confidence scoring result combining retrieval, reranking, citation, and answerability.",
    )

    model_config = ConfigDict(frozen=True)
