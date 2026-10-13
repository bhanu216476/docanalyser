"""
FastAPI router for queued document ingestion jobs.

Exposes:
    POST /api/v1/ingestion/jobs        — submit an add/update/delete ingestion job
    GET  /api/v1/ingestion/jobs/{id}   — poll a single job's state
    GET  /api/v1/ingestion/jobs        — list jobs, optionally filtered

The submission endpoint returns 202 Accepted immediately: the expensive
ingestion work (loading, chunking, embedding, Qdrant upsert, BM25 indexing)
runs on the background worker owned by ``IngestionJobService``.

Error mapping:
    IngestionQueueFullError    → HTTP 503 Service Unavailable
    IngestionJobNotFoundError  → HTTP 404 Not Found
    Pydantic validation errors → HTTP 422 (automatic via FastAPI)

The synchronous ingestion paths (``/api/v1/rag/ingest`` and
``/api/v1/documents``) are unchanged and remain available.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.jobs.exceptions import (
    IngestionJobError,
    IngestionJobNotFoundError,
    IngestionQueueFullError,
)
from app.jobs.models import (
    IngestionJobRequest,
    IngestionJobResponse,
    IngestionJobStatus,
)
from app.jobs.queue import IngestionJobQueue
from app.jobs.service import IngestionJobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])

# Global job service instance (injected or default)
_job_service: IngestionJobService | None = None


def get_job_service() -> IngestionJobService:
    """
    Return the active ``IngestionJobService``, creating the default one on
    first use. The default service reuses the pipeline-backed document
    lifecycle service so queued and synchronous ingestion share one index.
    """
    global _job_service
    if _job_service is None:
        from app.api.documents import get_document_lifecycle_service

        _job_service = IngestionJobService(
            lifecycle_service=get_document_lifecycle_service(),
            queue=IngestionJobQueue(
                max_size=settings.ingestion_queue_max_size,
                history_size=settings.ingestion_job_history_size,
            ),
            worker_enabled=settings.ingestion_worker_enabled,
        )
    return _job_service


def set_job_service(service: IngestionJobService | None) -> None:
    """Inject a custom or in-memory service instance (e.g. for testing)."""
    global _job_service
    _job_service = service


async def stop_worker_if_running() -> None:
    """
    Stop the background worker when a service has already been created.

    Deliberately does not instantiate a service: application shutdown must
    not build a RAG pipeline that was never used.
    """
    if _job_service is not None:
        await _job_service.stop_worker()


@router.post(
    "/jobs",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a queued document ingestion job",
    description=(
        "Create an add, update, or delete ingestion job and return immediately. "
        "The job is processed asynchronously by the background worker; poll "
        "GET /api/v1/ingestion/jobs/{job_id} for its state. Identical active "
        "jobs for the same document and operation are coalesced."
    ),
)
async def submit_ingestion_job(request: IngestionJobRequest) -> IngestionJobResponse:
    """Accept an ingestion job for asynchronous processing."""
    service = get_job_service()

    try:
        response = await service.submit_job(request)
    except IngestionQueueFullError as exc:
        logger.warning("Ingestion queue rejected submission: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except IngestionJobError as exc:  # pragma: no cover - defensive
        logger.error("Ingestion job submission failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit ingestion job.",
        ) from exc

    logger.info(
        "POST /api/v1/ingestion/jobs: job_id=%s document_id=%s operation=%s "
        "status=%s deduplicated=%s",
        response.job_id,
        response.document_id,
        response.operation.value,
        response.status.value,
        response.deduplicated,
    )
    return response


@router.get(
    "/jobs",
    response_model=list[IngestionJobResponse],
    summary="List ingestion jobs",
    description=(
        "List ingestion jobs ordered by submission time (newest first), "
        "optionally filtered by status or document_id."
    ),
    status_code=status.HTTP_200_OK,
)
async def list_ingestion_jobs(
    job_status: Annotated[
        IngestionJobStatus | None,
        Query(
            alias="status",
            description="Filter by job state: QUEUED, PROCESSING, COMPLETED, FAILED.",
        ),
    ] = None,
    document_id: Annotated[
        str | None,
        Query(min_length=1, description="Filter by document identifier."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Maximum jobs returned."),
    ] = 50,
) -> list[IngestionJobResponse]:
    """List ingestion jobs, newest first."""
    return get_job_service().list_jobs(
        status=job_status,
        document_id=document_id,
        limit=limit,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job status",
    description=(
        "Return the current state of an ingestion job, including chunk count "
        "on success and error details on failure."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_ingestion_job(job_id: str) -> IngestionJobResponse:
    """Return a single ingestion job's observable state."""
    service = get_job_service()

    try:
        job = await service.get_job(job_id)
    except IngestionJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return service.to_response(job)
