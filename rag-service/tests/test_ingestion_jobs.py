"""
Tests for queued (asynchronous) document ingestion jobs.

Coverage:
    Models:  request validation (operation, required source, blank ids).
    Queue:   FIFO ordering, duplicate suppression, bounded capacity,
             history pruning, queue position, status counts, state
             transitions.
    Service: asynchronous ADD / UPDATE / DELETE processing, terminal
             states, error capture, worker lifecycle, deterministic
             ``process_next_job`` execution, async ingestion orchestration.
    API:     POST /api/v1/ingestion/jobs (202, dedupe, 422, 503),
             GET /api/v1/ingestion/jobs/{id} (200, 404),
             GET /api/v1/ingestion/jobs (filters).
    E2E:     a real in-memory RAGPipeline indexes a document through the
             queued path and lands in Qdrant + BM25.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.api.documents import set_document_lifecycle_service
from app.api.jobs import set_job_service
from app.api.rag import set_pipeline
from app.jobs.exceptions import IngestionJobNotFoundError, IngestionQueueFullError
from app.jobs.models import (
    IngestionJobRequest,
    IngestionJobStatus,
    IngestionOperation,
)
from app.jobs.queue import IngestionJobQueue
from app.jobs.service import IngestionJobService
from app.main import app
from app.pipeline.document_lifecycle import DocumentLifecycleService
from app.pipeline.rag_pipeline import IngestionError, create_rag_pipeline
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeVectorStore:
    """Records document-level deletions requested by the lifecycle service."""

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_by_document_id(self, document_id: str) -> None:
        self.deleted.append(document_id)


class FakeBm25Index:
    """Records BM25 removals requested by the lifecycle service."""

    def __init__(self) -> None:
        self.removed: list[str] = []

    def remove_by_document_id(self, document_id: str) -> int:
        self.removed.append(document_id)
        return 1


class RecordingPipeline:
    """Minimal RAGPipeline stand-in recording ingestion calls."""

    def __init__(self, chunk_count: int = 3, fail_with: Exception | None = None):
        self.vector_store = FakeVectorStore()
        self.bm25_index = FakeBm25Index()
        self.ingested: list[tuple[Path, str | None, dict | None]] = []
        self.chunk_count = chunk_count
        self.fail_with = fail_with

    def ingest(
        self,
        source: str | Path,
        document_id: str | None = None,
        metadata: dict | None = None,
    ) -> SimpleNamespace:
        if self.fail_with is not None:
            raise self.fail_with
        self.ingested.append((Path(source), document_id, metadata))
        return SimpleNamespace(chunk_count=self.chunk_count)


def build_lifecycle(pipeline: RecordingPipeline) -> DocumentLifecycleService:
    """Build the real lifecycle service over a recording pipeline."""
    return DocumentLifecycleService(pipeline)  # type: ignore[arg-type]


def build_service(
    pipeline: RecordingPipeline | None = None,
    *,
    worker_enabled: bool = False,
    max_size: int = 100,
    history_size: int = 100,
) -> tuple[IngestionJobService, RecordingPipeline]:
    """Build an IngestionJobService over a recording pipeline."""
    recording = pipeline or RecordingPipeline()
    service = IngestionJobService(
        lifecycle_service=build_lifecycle(recording),
        queue=IngestionJobQueue(max_size=max_size, history_size=history_size),
        worker_enabled=worker_enabled,
    )
    return service, recording


def add_request(
    document_id: str = "doc-1",
    source: Path | str = "/tmp/report.txt",
    file_name: str = "report.txt",
    **extra: object,
) -> IngestionJobRequest:
    """Build a valid ADD job request."""
    return IngestionJobRequest(
        operation=IngestionOperation.ADD,
        document_id=document_id,
        source_url=str(source),
        file_name=file_name,
        **extra,  # type: ignore[arg-type]
    )


def delete_request(document_id: str = "doc-1") -> IngestionJobRequest:
    """Build a valid DELETE job request."""
    return IngestionJobRequest(
        operation=IngestionOperation.DELETE, document_id=document_id
    )


def run_jobs(
    service: IngestionJobService,
    requests: list[IngestionJobRequest],
) -> list[object]:
    """Submit and fully process jobs on a single event loop (deterministic)."""

    async def scenario() -> list[object]:
        service.start_worker()
        try:
            submitted = [await service.submit_job(request) for request in requests]
            return [
                await service.wait_for_job(job.job_id, timeout=10.0)  # type: ignore[attr-defined]
                for job in submitted
            ]
        finally:
            await service.stop_worker()

    return asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestIngestionJobRequestValidation:
    """Job submission payload validation."""

    def test_add_requires_source_url_and_file_name(self) -> None:
        with pytest.raises(ValueError, match="source_url is required"):
            IngestionJobRequest(operation=IngestionOperation.ADD, document_id="doc-1")

        with pytest.raises(ValueError, match="file_name is required"):
            IngestionJobRequest(
                operation=IngestionOperation.ADD,
                document_id="doc-1",
                source_url="/tmp/a.txt",
            )

    def test_update_requires_source_url(self) -> None:
        with pytest.raises(ValueError, match="source_url is required"):
            IngestionJobRequest(
                operation=IngestionOperation.UPDATE, document_id="doc-1"
            )

    def test_delete_does_not_require_source(self) -> None:
        request = delete_request()
        assert request.source_url is None
        assert request.file_name is None

    @pytest.mark.parametrize("document_id", ["", "   ", "\t"])
    def test_blank_document_id_is_rejected(self, document_id: str) -> None:
        with pytest.raises(ValueError):
            IngestionJobRequest(
                operation=IngestionOperation.DELETE, document_id=document_id
            )

    def test_unknown_operation_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IngestionJobRequest.model_validate(
                {"operation": "REINDEX", "document_id": "doc-1"}
            )

    def test_unknown_fields_are_rejected(self) -> None:
        with pytest.raises(ValueError):
            IngestionJobRequest.model_validate(
                {"operation": "DELETE", "document_id": "doc-1", "unexpected": True}
            )

    def test_request_is_immutable(self) -> None:
        request = add_request()
        with pytest.raises(ValueError):
            request.document_id = "other"  # type: ignore[misc]

    def test_job_status_terminality(self) -> None:
        assert IngestionJobStatus.QUEUED.is_active is True
        assert IngestionJobStatus.PROCESSING.is_active is True
        assert IngestionJobStatus.COMPLETED.is_terminal is True
        assert IngestionJobStatus.FAILED.is_terminal is True


# ---------------------------------------------------------------------------
# Queue behaviour
# ---------------------------------------------------------------------------


class TestIngestionJobQueue:
    """FIFO queue, dedupe, capacity, and state transition semantics."""

    def test_submit_creates_queued_job(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        job, deduplicated = queue.submit(add_request())

        assert deduplicated is False
        assert job.status is IngestionJobStatus.QUEUED
        assert job.operation is IngestionOperation.ADD
        assert job.started_at is None and job.finished_at is None
        assert queue.pending_count == 1
        assert len(queue) == 1
        assert queue.queue_position(job.job_id) == 1
        assert queue.get(job.job_id) == job

    def test_fifo_ordering_of_waiting_jobs(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        first, _ = queue.submit(add_request(document_id="doc-1"))
        second, _ = queue.submit(add_request(document_id="doc-2"))

        assert queue.queue_position(first.job_id) == 1
        assert queue.queue_position(second.job_id) == 2

    def test_duplicate_active_submission_is_coalesced(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        first, first_dup = queue.submit(add_request())
        second, second_dup = queue.submit(add_request())

        assert first_dup is False
        assert second_dup is True
        assert second.job_id == first.job_id
        assert queue.pending_count == 1

    def test_same_document_different_operation_is_not_duplicate(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        queue.submit(add_request(document_id="doc-1"))
        _, deduplicated = queue.submit(delete_request(document_id="doc-1"))

        assert deduplicated is False
        assert queue.pending_count == 2

    def test_terminal_job_allows_resubmission(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        first, _ = queue.submit(add_request())
        assert queue.queue_position(first.job_id) == 1
        queue.fail(first.job_id, error="boom", error_type="RuntimeError")

        second, deduplicated = queue.submit(add_request())
        assert deduplicated is False
        assert second.job_id != first.job_id

    def test_capacity_is_enforced(self) -> None:
        queue = IngestionJobQueue(max_size=2, history_size=5)
        queue.submit(add_request(document_id="doc-1"))
        queue.submit(add_request(document_id="doc-2"))

        with pytest.raises(IngestionQueueFullError):
            queue.submit(add_request(document_id="doc-3"))

        # Duplicates of already-queued work are still accepted (no growth).
        _, deduplicated = queue.submit(add_request(document_id="doc-1"))
        assert deduplicated is True

    def test_invalid_configuration_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IngestionJobQueue(max_size=0)
        with pytest.raises(ValueError):
            IngestionJobQueue(history_size=0)

    def test_list_jobs_filters_and_limit(self) -> None:
        queue = IngestionJobQueue(max_size=10, history_size=10)
        first, _ = queue.submit(add_request(document_id="doc-1"))
        queue.submit(add_request(document_id="doc-2"))
        queue.complete(first.job_id, chunk_count=4)

        assert len(queue.list_jobs()) == 2
        completed = queue.list_jobs(status=IngestionJobStatus.COMPLETED)
        assert [job.document_id for job in completed] == ["doc-1"]
        assert len(queue.list_jobs(document_id="doc-2")) == 1
        assert len(queue.list_jobs(limit=1)) == 1
        assert queue.counts_by_status() == {
            "QUEUED": 1,
            "PROCESSING": 0,
            "COMPLETED": 1,
            "FAILED": 0,
        }

    def test_list_jobs_rejects_invalid_limit(self) -> None:
        queue = IngestionJobQueue()
        with pytest.raises(ValueError):
            queue.list_jobs(limit=0)

    def test_history_pruning_evicts_terminal_records_only(self) -> None:
        queue = IngestionJobQueue(max_size=10, history_size=2)
        first, _ = queue.submit(add_request(document_id="doc-1"))
        queue.complete(first.job_id)
        second, _ = queue.submit(add_request(document_id="doc-2"))
        queue.complete(second.job_id)
        third, _ = queue.submit(add_request(document_id="doc-3"))

        assert queue.record_count == 2
        assert queue.get(first.job_id) is None
        assert queue.get(second.job_id) is not None
        assert queue.get(third.job_id) is not None

    def test_next_job_marks_processing_and_releases_fifo(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        job, _ = queue.submit(add_request())

        claimed = asyncio.run(queue.next_job())

        assert claimed is not None
        assert claimed.job_id == job.job_id
        assert claimed.status is IngestionJobStatus.PROCESSING
        assert claimed.started_at is not None
        assert queue.pending_count == 0
        assert queue.queue_position(job.job_id) is None

    def test_shutdown_releases_consumer(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        queue.shutdown()
        assert asyncio.run(queue.next_job()) is None

    def test_complete_and_fail_capture_terminal_state(self) -> None:
        queue = IngestionJobQueue(max_size=5, history_size=5)
        job, _ = queue.submit(add_request())

        completed = queue.complete(job.job_id, chunk_count=7)
        assert completed.status is IngestionJobStatus.COMPLETED
        assert completed.chunk_count == 7
        assert completed.finished_at is not None
        assert completed.error is None

        failed = queue.fail(
            job.job_id, error="embedding failed", error_type="EmbeddingError"
        )
        assert failed.status is IngestionJobStatus.FAILED
        assert failed.error == "embedding failed"
        assert failed.error_type == "EmbeddingError"


# ---------------------------------------------------------------------------
# Service: async processing
# ---------------------------------------------------------------------------


class TestIngestionJobServiceProcessing:
    """Asynchronous job execution, states, and error capture."""

    def test_job_stays_queued_when_worker_disabled(self, tmp_path: Path) -> None:
        """Without a worker the job is observable as QUEUED until claimed."""
        source = tmp_path / "report.txt"
        source.write_text("content", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=False)

        async def scenario() -> tuple[object, object]:
            submitted = await service.submit_job(add_request(source=source))
            assert submitted.status is IngestionJobStatus.QUEUED
            assert submitted.queue_position == 1
            assert service.worker_running is False
            return submitted, await service.process_next_job()

        _submitted, processed = asyncio.run(scenario())
        assert processed is not None
        assert processed.status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert processed.chunk_count == 3  # type: ignore[attr-defined]
        assert processed.started_at is not None  # type: ignore[attr-defined]
        assert processed.finished_at is not None  # type: ignore[attr-defined]
        assert pipeline.ingested == [(source, "doc-1", {})]
        response = service.to_response(processed)  # type: ignore[arg-type]
        assert response.queue_position is None
        assert response.status is IngestionJobStatus.COMPLETED

    def test_add_job_is_processed_with_worker(self, tmp_path: Path) -> None:
        source = tmp_path / "policy.txt"
        source.write_text("Casual leave is 12 days.", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=True)

        jobs = run_jobs(service, [add_request(source=source, file_name="policy.txt")])

        assert len(jobs) == 1
        job = jobs[0]
        assert job.status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert job.chunk_count == 3  # type: ignore[attr-defined]
        assert pipeline.ingested == [(source, "doc-1", {})]

    def test_lifecycle_metadata_is_propagated(self, tmp_path: Path) -> None:
        source = tmp_path / "policy.txt"
        source.write_text("Casual leave is 12 days.", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=True)

        request = add_request(
            source=source,
            file_name="policy.txt",
            metadata={"dept": "HR"},
            content_type="text/plain",
            version="2",
            updated_at="2026-01-01T00:00:00Z",
        )
        jobs = run_jobs(service, [request])

        assert jobs[0].status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert pipeline.ingested == [
            (
                source,
                "doc-1",
                {
                    "dept": "HR",
                    "content_type": "text/plain",
                    "version": "2",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )
        ]

    def test_update_job_removes_existing_index_entries(self, tmp_path: Path) -> None:
        source = tmp_path / "policy.txt"
        source.write_text("updated content", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=True)

        request = IngestionJobRequest(
            operation=IngestionOperation.UPDATE,
            document_id="doc-1",
            source_url=str(source),
            file_name="policy.txt",
        )
        jobs = run_jobs(service, [request])

        assert jobs[0].status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert pipeline.vector_store.deleted == ["doc-1"]
        assert pipeline.bm25_index.removed == ["doc-1"]
        assert pipeline.ingested == [(source, "doc-1", {})]

    def test_delete_job_removes_index_entries_without_ingestion(self) -> None:
        service, pipeline = build_service(worker_enabled=True)

        jobs = run_jobs(service, [delete_request()])

        job = jobs[0]
        assert job.status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert job.chunk_count == 0  # type: ignore[attr-defined]
        assert job.operation is IngestionOperation.DELETE  # type: ignore[attr-defined]
        assert pipeline.vector_store.deleted == ["doc-1"]
        assert pipeline.bm25_index.removed == ["doc-1"]
        assert pipeline.ingested == []

    def test_missing_source_fails_job_and_captures_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.txt"
        service, pipeline = build_service(worker_enabled=True)

        jobs = run_jobs(service, [add_request(source=missing)])

        job = jobs[0]
        assert job.status is IngestionJobStatus.FAILED  # type: ignore[attr-defined]
        assert "does not exist" in job.error  # type: ignore[attr-defined]
        assert job.error_type == "FileNotFoundError"  # type: ignore[attr-defined]
        assert job.finished_at is not None  # type: ignore[attr-defined]
        assert pipeline.ingested == []

    def test_ingestion_failure_is_captured_as_document_lifecycle_error(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.txt"
        source.write_text("content", encoding="utf-8")
        pipeline = RecordingPipeline(fail_with=IngestionError("embedding failed"))
        service, _ = build_service(pipeline=pipeline, worker_enabled=True)

        jobs = run_jobs(service, [add_request(source=source)])

        job = jobs[0]
        assert job.status is IngestionJobStatus.FAILED  # type: ignore[attr-defined]
        assert job.error == "embedding failed"  # type: ignore[attr-defined]
        assert job.error_type == "DocumentLifecycleError"  # type: ignore[attr-defined]

    def test_worker_survives_a_failed_job_and_processes_the_next(
        self, tmp_path: Path
    ) -> None:
        failing = tmp_path / "missing.txt"
        healthy = tmp_path / "report.txt"
        healthy.write_text("content", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=True)

        jobs = run_jobs(
            service,
            [
                add_request(
                    document_id="doc-bad", source=failing, file_name="missing.txt"
                ),
                add_request(
                    document_id="doc-good", source=healthy, file_name="report.txt"
                ),
            ],
        )

        assert jobs[0].status is IngestionJobStatus.FAILED  # type: ignore[attr-defined]
        assert jobs[1].status is IngestionJobStatus.COMPLETED  # type: ignore[attr-defined]
        assert pipeline.ingested == [(healthy, "doc-good", {})]
        assert service.queue.counts_by_status()["FAILED"] == 1
        assert service.queue.counts_by_status()["COMPLETED"] == 1

    def test_jobs_are_processed_fifo(self, tmp_path: Path) -> None:
        first_source = tmp_path / "first.txt"
        second_source = tmp_path / "second.txt"
        first_source.write_text("first", encoding="utf-8")
        second_source.write_text("second", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=True)

        run_jobs(
            service,
            [
                add_request(
                    document_id="doc-1", source=first_source, file_name="first.txt"
                ),
                add_request(
                    document_id="doc-2", source=second_source, file_name="second.txt"
                ),
            ],
        )

        assert [doc_id for _, doc_id, _ in pipeline.ingested] == ["doc-1", "doc-2"]

    def test_duplicate_submission_is_processed_once(self, tmp_path: Path) -> None:
        source = tmp_path / "report.txt"
        source.write_text("content", encoding="utf-8")
        service, pipeline = build_service(worker_enabled=False)
        request = add_request(source=source)

        async def scenario() -> tuple[object, object, object, object]:
            first = await service.submit_job(request)
            second = await service.submit_job(request)
            processed = await service.process_next_job()
            # Release the consumer so the empty-queue claim returns instead
            # of waiting for new work.
            service.queue.shutdown()
            empty = await service.process_next_job()
            return first, second, processed, empty

        first, second, processed, empty = asyncio.run(scenario())
        assert second.job_id == first.job_id  # type: ignore[attr-defined]
        assert second.deduplicated is True  # type: ignore[attr-defined]
        assert processed is not None
        assert empty is None
        assert len(pipeline.ingested) == 1


# ---------------------------------------------------------------------------
# Service: API helpers
# ---------------------------------------------------------------------------


class TestIngestionJobServiceHelpers:
    """Job lookup, listing, and async wrapper behaviour."""

    def test_get_and_list_jobs(self) -> None:
        service, _ = build_service(worker_enabled=False)
        request = add_request()

        async def scenario() -> None:
            response = await service.submit_job(request)
            job = await service.get_job(response.job_id)
            assert job.job_id == response.job_id
            listed = service.list_jobs(status=IngestionJobStatus.QUEUED)
            assert [item.job_id for item in listed] == [response.job_id]
            assert service.list_jobs(document_id="other") == []

        asyncio.run(scenario())

    def test_get_unknown_job_raises_not_found(self) -> None:
        service, _ = build_service(worker_enabled=False)

        async def scenario() -> None:
            with pytest.raises(IngestionJobNotFoundError):
                await service.get_job("does-not-exist")

        asyncio.run(scenario())

    def test_wait_for_job_times_out_when_never_processed(self) -> None:
        service, _ = build_service(worker_enabled=False)

        async def scenario() -> None:
            response = await service.submit_job(delete_request())
            with pytest.raises(TimeoutError):
                await service.wait_for_job(response.job_id, timeout=0.05)

        asyncio.run(scenario())

    def test_worker_start_is_disabled_by_configuration(self) -> None:
        service, _ = build_service(worker_enabled=False)

        async def scenario() -> bool:
            return service.start_worker()

        assert asyncio.run(scenario()) is False
        assert service.worker_running is False


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def poll_until_terminal(client: TestClient, job_id: str, timeout: float = 20.0) -> dict:
    """Poll a job's status endpoint until it reaches COMPLETED or FAILED."""
    deadline = time.monotonic() + timeout
    while True:
        response = client.get(f"/api/v1/ingestion/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("COMPLETED", "FAILED"):
            return body
        if time.monotonic() >= deadline:
            pytest.fail(f"job {job_id} did not finish in time: {body}")
        time.sleep(0.02)


@pytest.fixture
def queued_client():
    """TestClient with a recording pipeline and the worker disabled."""
    service, pipeline = build_service(worker_enabled=False, max_size=1)
    set_job_service(service)
    try:
        with TestClient(app) as client:
            yield client, service, pipeline
    finally:
        set_job_service(None)


@pytest.fixture
def pipeline_client():
    """TestClient with a real in-memory RAG pipeline and the worker enabled."""
    pipeline = create_rag_pipeline(in_memory=True)
    set_pipeline(pipeline)
    set_document_lifecycle_service(None)
    set_job_service(None)
    try:
        with TestClient(app) as client:
            yield client, pipeline
    finally:
        set_job_service(None)
        set_document_lifecycle_service(None)
        set_pipeline(None)


class TestIngestionJobApi:
    """POST/GET contract of the queued ingestion endpoints."""

    def test_submit_job_returns_202_and_queued_state(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            json={
                "operation": "ADD",
                "document_id": "doc-1",
                "file_name": "report.txt",
                "source_url": "/tmp/report.txt",
                "metadata": {"dept": "HR"},
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "QUEUED"
        assert body["operation"] == "ADD"
        assert body["document_id"] == "doc-1"
        assert body["file_name"] == "report.txt"
        assert body["queue_position"] == 1
        assert body["deduplicated"] is False
        assert body["chunk_count"] == 0
        assert body["error"] is None
        assert body["job_id"]

    def test_duplicate_submission_is_coalesced(self, queued_client) -> None:
        client, _, _ = queued_client
        payload = {
            "operation": "ADD",
            "document_id": "doc-1",
            "file_name": "report.txt",
            "source_url": "/tmp/report.txt",
        }

        first = client.post("/api/v1/ingestion/jobs", json=payload).json()
        second = client.post("/api/v1/ingestion/jobs", json=payload)

        assert second.status_code == 202
        assert second.json()["job_id"] == first["job_id"]
        assert second.json()["deduplicated"] is True

    def test_queue_full_returns_503(self, queued_client) -> None:
        client, _, _ = queued_client
        client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-1"},
        )

        response = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-2"},
        )

        assert response.status_code == 503
        assert "full" in response.json()["detail"].lower()

    def test_missing_source_url_returns_422(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "ADD", "document_id": "doc-1"},
        )

        assert response.status_code == 422

    def test_blank_document_id_returns_422(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "   "},
        )

        assert response.status_code == 422

    def test_unknown_operation_returns_422(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "REINDEX", "document_id": "doc-1"},
        )

        assert response.status_code == 422

    def test_malformed_body_returns_422(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            content="{not-json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_delete_job_without_source_is_accepted(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-1"},
        )

        assert response.status_code == 202
        assert response.json()["source_url"] is None

    def test_get_job_status(self, queued_client) -> None:
        client, _, _ = queued_client
        job_id = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-1"},
        ).json()["job_id"]

        response = client.get(f"/api/v1/ingestion/jobs/{job_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == job_id
        assert body["status"] == "QUEUED"
        assert body["created_at"]

    def test_get_unknown_job_returns_404(self, queued_client) -> None:
        client, _, _ = queued_client
        response = client.get("/api/v1/ingestion/jobs/unknown-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_jobs_with_filters(self, queued_client) -> None:
        client, _, _ = queued_client
        job_id = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-1"},
        ).json()["job_id"]

        listed = client.get("/api/v1/ingestion/jobs")
        assert listed.status_code == 200
        assert [job["job_id"] for job in listed.json()] == [job_id]

        filtered = client.get(
            "/api/v1/ingestion/jobs",
            params={"status": "QUEUED", "document_id": "doc-1", "limit": 1},
        )
        assert [job["job_id"] for job in filtered.json()] == [job_id]

        completed = client.get("/api/v1/ingestion/jobs", params={"status": "COMPLETED"})
        assert completed.json() == []

        invalid = client.get(
            "/api/v1/ingestion/jobs", params={"status": "NOT-A-STATUS"}
        )
        assert invalid.status_code == 422


# ---------------------------------------------------------------------------
# End-to-end: queue → ingestion → indexing → retrieval
# ---------------------------------------------------------------------------


class TestQueuedIngestionEndToEnd:
    """Queued ingestion drives the real pipeline (vector store + BM25)."""

    def test_add_job_indexes_document_and_delete_job_removes_it(
        self, pipeline_client, tmp_path: Path
    ) -> None:
        client, pipeline = pipeline_client
        source = tmp_path / "handbook.txt"
        source.write_text(
            "Casual leave entitlement is twelve days per calendar year. "
            "Sick leave requires a medical certificate.",
            encoding="utf-8",
        )

        submitted = client.post(
            "/api/v1/ingestion/jobs",
            json={
                "operation": "ADD",
                "document_id": "doc-queued",
                "file_name": "handbook.txt",
                "source_url": str(source),
            },
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]

        completed = poll_until_terminal(client, job_id)
        assert completed["status"] == "COMPLETED"
        assert completed["chunk_count"] > 0
        assert completed["error"] is None

        # Document reached the shared index: BM25 corpus and Qdrant collection.
        assert pipeline.bm25_index.num_documents == completed["chunk_count"]
        assert pipeline.vector_store.count() == completed["chunk_count"]

        # And it is retrievable through the existing BM25 retriever.
        hits = pipeline.bm25_retriever.retrieve("casual leave entitlement", top_k=3)
        assert hits
        assert hits[0].document_id == "doc-queued"

        # DELETE job removes both index representations again.
        deleted = client.post(
            "/api/v1/ingestion/jobs",
            json={"operation": "DELETE", "document_id": "doc-queued"},
        )
        assert deleted.status_code == 202
        delete_completed = poll_until_terminal(client, deleted.json()["job_id"])

        assert delete_completed["status"] == "COMPLETED"
        assert delete_completed["chunk_count"] == 0
        assert pipeline.bm25_index.num_documents == 0
        assert pipeline.vector_store.count() == 0

    def test_update_job_replaces_existing_chunks(
        self, pipeline_client, tmp_path: Path
    ) -> None:
        client, pipeline = pipeline_client
        source = tmp_path / "handbook.txt"
        source.write_text("Original policy text about annual leave.", encoding="utf-8")

        add_job = client.post(
            "/api/v1/ingestion/jobs",
            json={
                "operation": "ADD",
                "document_id": "doc-queued",
                "file_name": "handbook.txt",
                "source_url": str(source),
            },
        ).json()
        first = poll_until_terminal(client, add_job["job_id"])
        assert first["status"] == "COMPLETED"

        source.write_text(
            "Updated remote working policy with equipment allowance details.",
            encoding="utf-8",
        )
        update_job = client.post(
            "/api/v1/ingestion/jobs",
            json={
                "operation": "UPDATE",
                "document_id": "doc-queued",
                "file_name": "handbook.txt",
                "source_url": str(source),
            },
        ).json()
        second = poll_until_terminal(client, update_job["job_id"])

        assert second["status"] == "COMPLETED"
        assert pipeline.bm25_index.num_documents == second["chunk_count"]
        assert pipeline.vector_store.count() == second["chunk_count"]

    def test_failing_job_is_observable_through_the_api(
        self, pipeline_client, tmp_path: Path
    ) -> None:
        client, _ = pipeline_client
        missing = tmp_path / "missing.txt"

        submitted = client.post(
            "/api/v1/ingestion/jobs",
            json={
                "operation": "ADD",
                "document_id": "doc-missing",
                "file_name": "missing.txt",
                "source_url": str(missing),
            },
        ).json()
        body = poll_until_terminal(client, submitted["job_id"])

        assert body["status"] == "FAILED"
        assert "does not exist" in body["error"]
        assert body["error_type"] == "FileNotFoundError"

    def test_synchronous_ingestion_path_still_works(
        self, pipeline_client, tmp_path: Path
    ) -> None:
        """The pre-existing synchronous documents endpoint is unaffected."""
        client, pipeline = pipeline_client
        source = tmp_path / "sync.txt"
        source.write_text("Synchronous ingestion still works.", encoding="utf-8")

        response = client.post(
            "/api/v1/documents",
            json={
                "event": "DOCUMENT_ADDED",
                "document_id": "doc-sync",
                "file_name": "sync.txt",
                "source_url": str(source),
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "PROCESSED"
        assert pipeline.bm25_index.num_documents > 0
