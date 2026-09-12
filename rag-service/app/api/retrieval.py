"""
FastAPI router for dense retrieval.

Exposes:
    POST /api/retrieval/dense  — execute a dense vector similarity search

This endpoint is an internal service endpoint for the RAG pipeline.
It is NOT the final public query API (which will include LLM generation
and citation rendering — future tasks).

Error mapping:
    RetrievalQueryError       → HTTP 422 Unprocessable Entity
    RetrievalEmbeddingError   → HTTP 503 Service Unavailable
    RetrievalQdrantError      → HTTP 503 Service Unavailable
    Pydantic ValidationError  → HTTP 422 (automatic via FastAPI)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.retrieval.dense_retriever import create_dense_retriever
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import RetrievalRequest, RetrievalResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post(
    "/dense",
    response_model=list[RetrievalResult],
    summary="Dense vector retrieval",
    description=(
        "Execute a dense (vector) similarity search against the Qdrant collection. "
        "Returns the top-K most similar chunks ordered by similarity score. "
        "Optionally filters by document_id, file_type, source, or other metadata fields."
    ),
    status_code=status.HTTP_200_OK,
)
def dense_retrieve(request: RetrievalRequest) -> list[RetrievalResult]:
    """
    Dense retrieval endpoint.

    Flow:
        query → EmbeddingService → query vector → Qdrant search → RetrievalResult[]

    Example request::

        POST /api/retrieval/dense
        {
            "query": "How many casual leave days?",
            "top_k": 10
        }

    Example request with filter::

        POST /api/retrieval/dense
        {
            "query": "How many casual leave days?",
            "top_k": 5,
            "filters": {"document_id": "hr-policy-doc-123"}
        }
    """
    logger.info(
        "POST /api/retrieval/dense: query_len=%d, top_k=%d, has_filter=%s",
        len(request.query),
        request.top_k,
        request.filters is not None,
    )

    retriever = create_dense_retriever()

    try:
        results = retriever.retrieve_from_request(request)
    except RetrievalQueryError as exc:
        logger.warning("Dense retrieval query validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RetrievalEmbeddingError as exc:
        logger.error("Dense retrieval embedding failed (transient=%s): %s", exc.is_transient, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service unavailable. Please retry.",
        ) from exc
    except RetrievalQdrantError as exc:
        logger.error("Dense retrieval Qdrant search failed (transient=%s): %s", exc.is_transient, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector search service unavailable. Please retry.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during dense retrieval: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during retrieval.",
        ) from exc

    logger.info(
        "POST /api/retrieval/dense: returned %d results for top_k=%d",
        len(results),
        request.top_k,
    )
    return results
