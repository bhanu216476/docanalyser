"""
Pipeline package for DocAnalyser RAG V0.1.

Exports:
    - RAGPipeline: End-to-end RAG orchestrator.
    - create_rag_pipeline: Factory for pipeline instances.
    - RAGPipelineError, IngestionError, QueryPipelineError: Exceptions.
    - IngestionResponse, RAGQueryRequest, RAGResponse: Pydantic pipeline models.
"""

from app.pipeline.models import IngestionResponse, RAGQueryRequest, RAGResponse
from app.pipeline.rag_pipeline import (
    IngestionError,
    QueryPipelineError,
    RAGPipeline,
    RAGPipelineError,
    create_rag_pipeline,
)

__all__ = [
    "RAGPipeline",
    "create_rag_pipeline",
    "RAGPipelineError",
    "IngestionError",
    "QueryPipelineError",
    "IngestionResponse",
    "RAGQueryRequest",
    "RAGResponse",
]
