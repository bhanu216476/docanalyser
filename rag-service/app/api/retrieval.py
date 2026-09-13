"""
FastAPI router for retrieval (Dense and BM25 lexical).

Exposes:
    POST /api/retrieval/dense  — execute a dense vector similarity search
    POST /api/retrieval/bm25   — execute a BM25 lexical retrieval search

This router contains internal service endpoints for the RAG pipeline.
It is NOT the final public query API (which will include LLM generation
and citation rendering — future tasks).

Error mapping:
    RetrievalQueryError       → HTTP 422 Unprocessable Entity
    RetrievalEmbeddingError   → HTTP 503 Service Unavailable
    RetrievalQdrantError      → HTTP 503 Service Unavailable
    RetrievalIndexError       → HTTP 500 Internal Server Error
    Pydantic ValidationError  → HTTP 422 (automatic via FastAPI)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.retrieval.bm25_retriever import BM25Retriever, create_bm25_retriever
from app.retrieval.dense_retriever import create_dense_retriever
from app.retrieval.exceptions import (
    RetrievalEmbeddingError,
    RetrievalIndexError,
    RetrievalQdrantError,
    RetrievalQueryError,
)
from app.retrieval.models import RetrievalRequest, RetrievalResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])

# Global BM25 retriever instance (injected or default)
_bm25_retriever: Optional[BM25Retriever] = None


def get_bm25_retriever() -> BM25Retriever:
    """Return the active BM25Retriever instance, creating default if not set."""
    global _bm25_retriever
    if _bm25_retriever is None:
        _bm25_retriever = create_bm25_retriever()
    return _bm25_retriever


def set_bm25_retriever(retriever: BM25Retriever) -> None:
    """Set or override the active BM25Retriever instance (useful for testing)."""
    global _bm25_retriever
    _bm25_retriever = retriever


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


@router.post(
    "/bm25",
    response_model=list[RetrievalResult],
    summary="BM25 lexical retrieval",
    description=(
        "Execute a BM25 sparse keyword retrieval search against the indexed chunk corpus. "
        "Returns the top-K highest-scoring chunks ordered by descending BM25 score. "
        "Optionally filters by document_id, file_type, source, or other metadata fields."
    ),
    status_code=status.HTTP_200_OK,
)
def bm25_retrieve(request: RetrievalRequest) -> list[RetrievalResult]:
    """
    BM25 lexical retrieval endpoint.

    Flow:
        query → tokenize → pre-filter → BM25 score → tie-break → top_k → RetrievalResult[]
    """
    logger.info(
        "POST /api/retrieval/bm25: query_len=%d, top_k=%d, has_filter=%s",
        len(request.query),
        request.top_k,
        request.filters is not None,
    )

    retriever = get_bm25_retriever()

    try:
        results = retriever.retrieve_from_request(request)
    except RetrievalQueryError as exc:
        logger.warning("BM25 retrieval query validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RetrievalIndexError as exc:
        logger.error("BM25 retrieval index failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lexical search index failure.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during BM25 retrieval: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during retrieval.",
        ) from exc

    logger.info(
        "POST /api/retrieval/bm25: returned %d results for top_k=%d",
        len(results),
        request.top_k,
    )
    return results
