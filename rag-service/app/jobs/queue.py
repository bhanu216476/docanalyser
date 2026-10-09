"""
In-memory, asyncio-based FIFO queue for document ingestion jobs.

Responsibilities:
    ✓ Hold submitted jobs until a worker claims them (FIFO order)
    ✓ Suppress duplicate submissions for the same active
      (document_id, operation) pair
    ✓ Enforce a bounded queue capacity and a bounded record history
    ✓ Own every job state transition (QUEUED → PROCESSING → COMPLETED/FAILED)
    ✓ Expose queue introspection used by the status API

Explicitly out of scope:
    ✗ Executing ingestion (that is ``IngestionJobService`` / the worker)
    ✗ Persistence — this is an in-process queue, matching the project's
      current infrastructure (the Python service has no Redis/Celery
      requirement; Redis-backed document state is owned by Spring Boot).

Concurrency:
    All state is mutated from the event loop thread. ``next_job()`` is the
    only blocking call and is designed to be awaited by a single worker, so
    a job can never be claimed twice.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from uuid import uuid4

from app.jobs.exceptions import IngestionQueueFullError
from app.jobs.models import (
    IngestionJob,
    IngestionJobRequest,
    IngestionJobStatus,
    IngestionOperation,
    utc_now,
)

logger = logging.getLogger(__name__)

#: Sentinel pushed into the pending channel to release a blocked consumer.
_SHUTDOWN: None = None


class IngestionJobQueue:
    """
    Bounded in-memory FIFO queue of ingestion jobs.

    Args:
        max_size: Maximum number of jobs allowed to wait in the queue.
                  Distinct submissions beyond this limit raise
                  ``IngestionQueueFullError``.
        history_size: Maximum number of job records retained in memory.
                      The oldest terminal records are evicted first.
        job_id_factory: Optional job identifier factory (tests can inject a
                        deterministic sequence).
    """

    def __init__(
        self,
        *,
        max_size: int = 100,
        history_size: int = 500,
        job_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        if history_size <= 0:
            raise ValueError(f"history_size must be positive, got {history_size}")

        self._max_size = max_size
        self._history_size = history_size
        self._job_id_factory = job_id_factory or (lambda: uuid4().hex)
        self._jobs: dict[str, IngestionJob] = {}
        self._queued_ids: deque[str] = deque()
        self._pending: asyncio.Queue[str | None] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def max_size(self) -> int:
        """Configured maximum number of waiting jobs."""
        return self._max_size

    @property
    def history_size(self) -> int:
        """Configured maximum number of retained job records."""
        return self._history_size

    @property
    def pending_count(self) -> int:
        """Number of jobs currently waiting to be claimed."""
        return len(self._queued_ids)

    @property
    def record_count(self) -> int:
        """Number of job records currently retained."""
        return len(self._jobs)

    def __len__(self) -> int:
        """Return the number of waiting jobs (mirrors ``pending_count``)."""
        return len(self._queued_ids)

    def get(self, job_id: str) -> IngestionJob | None:
        """Return the job record for ``job_id``, or None when unknown."""
        return self._jobs.get(job_id)

    def find_active_job(
        self,
        document_id: str,
        operation: IngestionOperation,
    ) -> IngestionJob | None:
        """
        Return the active (QUEUED or PROCESSING) job for a document and
        operation, enabling duplicate submission suppression.
        """
        for job in self._jobs.values():
            if (
                job.document_id == document_id
                and job.operation == operation
                and job.status.is_active
            ):
                return job
        return None

    def queue_position(self, job_id: str) -> int | None:
        """Return the 1-based FIFO position of a waiting job, else None."""
        for position, queued_id in enumerate(self._queued_ids, start=1):
            if queued_id == job_id:
                return position
        return None

    def counts_by_status(self) -> dict[str, int]:
        """Return the number of retained jobs per status value."""
        counts = {state.value: 0 for state in IngestionJobStatus}
        for job in self._jobs.values():
            counts[job.status.value] += 1
        return counts

    def list_jobs(
        self,
        *,
        status: IngestionJobStatus | None = None,
        document_id: str | None = None,
        limit: int | None = None,
        newest_first: bool = True,
    ) -> list[IngestionJob]:
        """
        List job records, optionally filtered by state or document.

        Args:
            status: Restrict to a single job state.
            document_id: Restrict to a single document.
            limit: Maximum number of records returned (must be positive).
            newest_first: Order by submission time descending when True.
        """
        if limit is not None and limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")

        jobs = [
            job
            for job in self._jobs.values()
            if (status is None or job.status == status)
            and (document_id is None or job.document_id == document_id)
        ]
        jobs.sort(key=lambda job: (job.created_at, job.job_id), reverse=newest_first)
        return jobs[:limit] if limit is not None else jobs

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(self, request: IngestionJobRequest) -> tuple[IngestionJob, bool]:
        """
        Create and enqueue a job for ``request``.

        Returns:
            ``(job, deduplicated)`` where ``deduplicated`` is True when an
            identical active job already existed and was returned instead of
            creating a second one.

        Raises:
            IngestionQueueFullError: If the queue is at capacity and the
                submission is not a duplicate.
        """
        existing = self.find_active_job(request.document_id, request.operation)
        if existing is not None:
            logger.info(
                "Duplicate ingestion job suppressed: document_id=%s "
                "operation=%s job_id=%s",
                request.document_id,
                request.operation.value,
                existing.job_id,
            )
            return existing, True

        if len(self._queued_ids) >= self._max_size:
            raise IngestionQueueFullError(
                f"Ingestion queue is full ({self._max_size} jobs waiting). "
                "Retry after the current jobs complete."
            )

        job = IngestionJob(
            job_id=self._job_id_factory(),
            status=IngestionJobStatus.QUEUED,
            created_at=utc_now(),
            **request.model_dump(),
        )
        self._jobs[job.job_id] = job
        self._queued_ids.append(job.job_id)
        self._pending.put_nowait(job.job_id)
        self._prune_history()

        logger.info(
            "Ingestion job queued: job_id=%s document_id=%s operation=%s position=%d",
            job.job_id,
            job.document_id,
            job.operation.value,
            len(self._queued_ids),
        )
        return job, False

    # ------------------------------------------------------------------
    # Claiming and state transitions
    # ------------------------------------------------------------------

    async def next_job(self) -> IngestionJob | None:
        """
        Wait for the next queued job, claim it, and mark it PROCESSING.

        Returns:
            The claimed job, or None when the queue has been shut down.
        """
        while True:
            job_id = await self._pending.get()
            if job_id is _SHUTDOWN:
                logger.debug("Ingestion queue consumer released for shutdown")
                return None

            job = self._jobs.get(job_id)
            if job is None or job.status is not IngestionJobStatus.QUEUED:
                # Already claimed, evicted by history pruning, or cancelled.
                self._discard_queued_id(job_id)
                continue

            self._discard_queued_id(job_id)
            return self._update(
                job_id,
                status=IngestionJobStatus.PROCESSING,
                started_at=utc_now(),
            )

    def shutdown(self) -> None:
        """Release a blocked consumer so it can exit cleanly."""
        self._pending.put_nowait(_SHUTDOWN)

    def complete(self, job_id: str, *, chunk_count: int = 0) -> IngestionJob:
        """Mark a job COMPLETED with the number of indexed chunks."""
        return self._update(
            job_id,
            status=IngestionJobStatus.COMPLETED,
            finished_at=utc_now(),
            chunk_count=chunk_count,
            error=None,
            error_type=None,
        )

    def fail(
        self,
        job_id: str,
        *,
        error: str,
        error_type: str | None = None,
    ) -> IngestionJob:
        """Mark a job FAILED and capture the error information."""
        return self._update(
            job_id,
            status=IngestionJobStatus.FAILED,
            finished_at=utc_now(),
            error=error,
            error_type=error_type,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update(self, job_id: str, **changes: object) -> IngestionJob:
        """Apply ``changes`` to a job, replacing the frozen record."""
        job = self._jobs[job_id]
        updated = job.model_copy(update=changes)
        self._jobs[job_id] = updated
        return updated

    def _discard_queued_id(self, job_id: str) -> None:
        """Remove a job identifier from the waiting FIFO, if present."""
        try:
            self._queued_ids.remove(job_id)
        except ValueError:
            pass

    def _prune_history(self) -> None:
        """Evict oldest terminal records once the history limit is exceeded."""
        excess = len(self._jobs) - self._history_size
        if excess <= 0:
            return

        for job_id in list(self._jobs):
            if excess <= 0:
                break
            if self._jobs[job_id].status.is_terminal:
                del self._jobs[job_id]
                excess -= 1
