"""
Async orchestration of queued document ingestion jobs.

Pipeline position:
    POST /api/v1/ingestion/jobs
        ↓
    IngestionJobService.submit_job()   ← returns immediately (202 Accepted)
        ↓
    IngestionJobQueue (QUEUED)
        ↓
    background worker → DocumentLifecycleService.process_async()
        ↓
    add / update / delete of the document in Qdrant + BM25
        ↓
    IngestionJob (PROCESSING → COMPLETED | FAILED)

Design decisions:
    - The queued path delegates to the existing ``DocumentLifecycleService``,
      so document lifecycle behaviour (delete-then-ingest on update,
      metadata propagation, `DocumentLifecycleError` semantics) is identical
      to the synchronous ``/api/v1/documents`` endpoint.
    - Loaders, chunkers, embedding providers, Qdrant and BM25 are
      synchronous libraries. The worker isolates them with
      ``asyncio.to_thread`` instead of pretending they are async, and it
      serialises execution (single worker + processing lock) so concurrent
      jobs can never corrupt the shared in-memory BM25 index or the vector
      collection.
    - Job failures are captured on the record; a failing job never
      terminates the worker.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from app.core.config import settings
from app.jobs.exceptions import IngestionJobNotFoundError
from app.jobs.models import (
    IngestionJob,
    IngestionJobRequest,
    IngestionJobResponse,
    IngestionJobStatus,
    IngestionOperation,
)
from app.jobs.queue import IngestionJobQueue

logger = logging.getLogger(__name__)

#: Mapping from queued ingestion operation to document lifecycle event.
_OPERATION_TO_EVENT: dict[IngestionOperation, str] = {
    IngestionOperation.ADD: "DOCUMENT_ADDED",
    IngestionOperation.UPDATE: "DOCUMENT_UPDATED",
    IngestionOperation.DELETE: "DOCUMENT_DELETED",
}

#: Default interval used while polling for job completion.
DEFAULT_POLL_INTERVAL_SECONDS: float = 0.01


class IngestionJobService:
    """
    Submit, track, and process document ingestion jobs asynchronously.

    Args:
        lifecycle_service: Existing ``DocumentLifecycleService`` (or a duck
            typed equivalent exposing ``process``) used to perform the
            actual add / update / delete work.
        queue: Queue implementation. Defaults to a bounded in-memory queue
            configured from settings.
        worker_enabled: When False the background worker is never started and
            jobs stay QUEUED until ``process_next_job()`` is awaited
            explicitly (used by deterministic tests).
    """

    def __init__(
        self,
        lifecycle_service: Any,
        queue: Optional[IngestionJobQueue] = None,
        *,
        worker_enabled: bool = True,
    ) -> None:
        self.lifecycle_service = lifecycle_service
        self.queue = queue if queue is not None else IngestionJobQueue(
            max_size=settings.ingestion_queue_max_size,
            history_size=settings.ingestion_job_history_size,
        )
        self.worker_enabled = worker_enabled
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._processing_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    @property
    def worker_running(self) -> bool:
        """Return True while the background worker task is alive."""
        return self._worker_task is not None and not self._worker_task.done()

    def start_worker(self) -> bool:
        """
        Start the background worker on the running event loop.

        Returns:
            True when a worker was started, False when it was already running
            or disabled by configuration.

        Raises:
            RuntimeError: If no event loop is running in this thread.
        """
        if not self.worker_enabled:
            return False
        if self.worker_running:
            return False

        loop = asyncio.get_running_loop()
        self._worker_task = loop.create_task(
            self._worker_loop(), name="ingestion-job-worker"
        )
        logger.info(
            "Ingestion job worker started (queue_capacity=%d)",
            self.queue.max_size,
        )
        return True

    async def stop_worker(self) -> None:
        """Cancel the background worker and wait for it to finish."""
        task = self._worker_task
        self._worker_task = None
        if task is None:
            return

        self.queue.shutdown()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Ingestion job worker stopped")

    async def _worker_loop(self) -> None:
        """Continuously claim and process jobs until cancelled or shut down."""
        while True:
            job = await self.queue.next_job()
            if job is None:
                return
            await self._process_job(job)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_job(self, request: IngestionJobRequest) -> IngestionJobResponse:
        """
        Enqueue an ingestion job and return immediately.

        The queue performs duplicate suppression for identical active
        (document_id, operation) submissions. Starting the worker is best
        effort: if no event loop is running the job simply stays QUEUED.

        Raises:
            IngestionQueueFullError: When the queue is saturated.
        """
        job, deduplicated = self.queue.submit(request)
        if not deduplicated:
            self._ensure_worker()
        return self.to_response(job, deduplicated=deduplicated)

    async def get_job(self, job_id: str) -> IngestionJob:
        """
        Return a job record by identifier.

        Raises:
            IngestionJobNotFoundError: When the identifier is unknown.
        """
        job = self.queue.get(job_id)
        if job is None:
            raise IngestionJobNotFoundError(f"Ingestion job not found: {job_id}")
        return job

    def list_jobs(
        self,
        *,
        status: Optional[IngestionJobStatus] = None,
        document_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[IngestionJobResponse]:
        """List job records as API responses, with optional filters."""
        return [
            self.to_response(job)
            for job in self.queue.list_jobs(
                status=status, document_id=document_id, limit=limit
            )
        ]

    def to_response(
        self,
        job: IngestionJob,
        *,
        deduplicated: bool = False,
    ) -> IngestionJobResponse:
        """Project a job record into its API response form."""
        return IngestionJobResponse(
            **job.model_dump(),
            deduplicated=deduplicated,
            queue_position=self.queue.queue_position(job.job_id),
        )

    async def process_next_job(self) -> Optional[IngestionJob]:
        """
        Claim and process a single queued job.

        Used by the background worker and by tests that need deterministic,
        explicitly driven execution. Returns None when the queue is empty or
        shut down.
        """
        job = await self.queue.next_job()
        if job is None:
            return None
        return await self._process_job(job)

    async def wait_for_job(
        self,
        job_id: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> IngestionJob:
        """
        Await the terminal state (COMPLETED or FAILED) of a job.

        Only useful when the worker runs on the same event loop.

        Raises:
            IngestionJobNotFoundError: When the identifier is unknown.
            TimeoutError: When the job does not reach a terminal state in time.
        """
        deadline = time.monotonic() + timeout
        while True:
            job = await self.get_job(job_id)
            if job.is_terminal:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Ingestion job {job_id} did not reach a terminal state "
                    f"within {timeout} seconds (status={job.status.value})"
                )
            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_worker(self) -> None:
        """Start the background worker when enabled and a loop is running."""
        if not self.worker_enabled:
            return
        try:
            self.start_worker()
        except RuntimeError:  # pragma: no cover - no running loop
            logger.warning(
                "No running event loop: ingestion job will remain QUEUED "
                "until the worker is started"
            )

    async def _process_job(self, job: IngestionJob) -> IngestionJob:
        """
        Execute a single job and persist its terminal state.

        Never raises on ingestion failure: the failure is recorded on the
        job record so the worker keeps draining the queue.
        """
        request = self._build_lifecycle_request(job)
        async with self._processing_lock:
            try:
                result = await self._run_lifecycle(request)
            except Exception as exc:  # noqa: BLE001 - captured on the job
                logger.error(
                    "Ingestion job failed: job_id=%s document_id=%s "
                    "operation=%s error=%s",
                    job.job_id,
                    job.document_id,
                    job.operation.value,
                    exc,
                )
                return self.queue.fail(
                    job.job_id,
                    error=str(exc) or type(exc).__name__,
                    error_type=type(exc).__name__,
                )

        chunk_count = 0
        if isinstance(result, dict):
            try:
                chunk_count = int(result.get("chunk_count", 0) or 0)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                chunk_count = 0

        logger.info(
            "Ingestion job completed: job_id=%s document_id=%s operation=%s chunks=%d",
            job.job_id,
            job.document_id,
            job.operation.value,
            chunk_count,
        )
        return self.queue.complete(job.job_id, chunk_count=chunk_count)

    async def _run_lifecycle(self, request: Any) -> Any:
        """
        Run the document lifecycle operation without blocking the event loop.

        Uses ``DocumentLifecycleService.process_async`` when available and
        falls back to isolating the synchronous ``process`` in a worker
        thread for duck-typed substitutes.
        """
        process_async = getattr(self.lifecycle_service, "process_async", None)
        if process_async is not None:
            return await process_async(request)
        return await asyncio.to_thread(self.lifecycle_service.process, request)

    @staticmethod
    def _build_lifecycle_request(job: IngestionJob) -> Any:
        """Project a job record onto the existing document lifecycle request."""
        from app.api.documents import DocumentEvent, DocumentLifecycleRequest

        return DocumentLifecycleRequest(
            event=DocumentEvent(_OPERATION_TO_EVENT[job.operation]),
            document_id=job.document_id,
            file_name=job.file_name,
            source_url=job.source_url,
            content_type=job.content_type,
            metadata=dict(job.metadata),
            version=job.version,
            updated_at=job.updated_at,
        )
