"""
Integration tests for n8n automation and internal FastAPI document ingestion.

Verifies:
  1. Internal authentication enforcement via X-Internal-Token and Authorization: Bearer.
  2. Backward compatibility when no internal token is configured.
  3. Remote document ingestion (HTTP/HTTPS) support in DocumentLifecycleService.
  4. Queued asynchronous job processing for remote documents.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import verify_internal_token
from app.api.documents import DocumentEvent, DocumentLifecycleRequest, set_document_lifecycle_service
from app.api.jobs import set_job_service
from app.core.config import settings
from app.jobs.models import IngestionJobRequest, IngestionOperation
from app.jobs.queue import IngestionJobQueue
from app.jobs.service import IngestionJobService
from app.main import app
from app.pipeline.document_lifecycle import DocumentLifecycleService


class FakePipeline:
    def __init__(self):
        self.vector_store = MagicMock()
        self.bm25_index = MagicMock()
        self.ingested = []

    def ingest(self, source, document_id=None, metadata=None):
        content = Path(source).read_text(encoding="utf-8")
        self.ingested.append((content, document_id, metadata))
        return SimpleNamespace(chunk_count=3)


@pytest.fixture
def test_client():
    return TestClient(app)


def test_auth_bypassed_when_token_empty():
    """When N8N_INGESTION_TOKEN is unset/empty, all requests are allowed."""
    with patch.object(settings, "n8n_ingestion_token", ""):
        assert verify_internal_token() is True


def test_auth_enforces_token_when_configured(test_client):
    """When N8N_INGESTION_TOKEN is set, requests without matching token receive 401."""
    with patch.object(settings, "n8n_ingestion_token", "secret-test-token"):
        # 1. Missing token
        resp = test_client.get("/api/v1/ingestion/jobs")
        assert resp.status_code == 401
        assert "Invalid or missing" in resp.json()["detail"]

        # 2. Wrong token
        resp = test_client.get(
            "/api/v1/ingestion/jobs",
            headers={"X-Internal-Token": "wrong-token"},
        )
        assert resp.status_code == 401

        # 3. Valid X-Internal-Token
        resp = test_client.get(
            "/api/v1/ingestion/jobs",
            headers={"X-Internal-Token": "secret-test-token"},
        )
        assert resp.status_code == 200

        # 4. Valid Authorization: Bearer token
        resp = test_client.get(
            "/api/v1/ingestion/jobs",
            headers={"Authorization": "Bearer secret-test-token"},
        )
        assert resp.status_code == 200


def test_lifecycle_processes_remote_url():
    """DocumentLifecycleService downloads remote documents via HTTP and ingests them."""
    pipeline = FakePipeline()
    service = DocumentLifecycleService(pipeline)

    remote_content = b"Contract terms and clauses for enterprise SLA."
    fake_response = MagicMock()
    fake_response.content = remote_content
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = fake_response
        mock_client_cls.return_value = mock_client

        req = DocumentLifecycleRequest(
            event=DocumentEvent.DOCUMENT_ADDED,
            document_id="doc-remote-123",
            file_name="agreement.txt",
            source_url="https://cloud.docanalyser.com/docs/agreement.txt",
            metadata={"source": "n8n-webhook"},
        )

        result = service.process(req)

        assert result["success"] is True
        assert result["document_id"] == "doc-remote-123"
        assert result["chunk_count"] == 3
        assert len(pipeline.ingested) == 1
        assert pipeline.ingested[0][0] == "Contract terms and clauses for enterprise SLA."
        assert pipeline.ingested[0][1] == "doc-remote-123"
        assert pipeline.ingested[0][2]["source"] == "n8n-webhook"


@pytest.mark.anyio
async def test_async_job_service_processes_remote_document():
    """Asynchronous IngestionJobService claims and finishes a remote document job."""
    pipeline = FakePipeline()
    lifecycle_service = DocumentLifecycleService(pipeline)
    queue = IngestionJobQueue(max_size=10, history_size=10)
    job_service = IngestionJobService(
        lifecycle_service=lifecycle_service,
        queue=queue,
        worker_enabled=False,
    )

    fake_response = MagicMock()
    fake_response.content = b"Sample policy document from cloud storage."
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = fake_response
        mock_client_cls.return_value = mock_client

        job_req = IngestionJobRequest(
            operation=IngestionOperation.ADD,
            document_id="doc-async-999",
            file_name="policy.txt",
            source_url="https://cloud.docanalyser.com/policy.txt",
        )

        sub_resp = await job_service.submit_job(job_req)
        assert sub_resp.status.value == "QUEUED"
        assert sub_resp.job_id is not None

        # Process next job
        completed_job = await job_service.process_next_job()
        assert completed_job is not None
        assert completed_job.status.value == "COMPLETED"
        assert completed_job.chunk_count == 3
        assert len(pipeline.ingested) == 1


def test_n8n_workflow_json_schema():
    """Verify that the generated n8n workflow is valid JSON and targets the deployed Render HTTPS endpoints."""
    import json

    workflow_path = (
        Path(__file__).resolve().parent.parent.parent
        / "infrastructure"
        / "n8n"
        / "docanalyser_rag_ingestion_workflow.json"
    )
    assert workflow_path.exists(), f"Workflow file missing: {workflow_path}"

    with workflow_path.open(encoding="utf-8") as f:
        workflow = json.load(f)

    assert "nodes" in workflow
    assert "connections" in workflow
    node_names = [n["name"] for n in workflow["nodes"]]

    assert "Webhook - Ingestion Trigger" in node_names
    assert "Submit Job to FastAPI" in node_names
    assert "Poll Job Status" in node_names
    assert "Respond - Success 200" in node_names

    # Check endpoints in HTTP Request nodes
    http_nodes = [n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"]
    for node in http_nodes:
        url = node["parameters"]["url"]
        assert "localhost" not in url, f"Production workflow must not contain localhost: {url}"
        assert "https://docanalyser-rag.onrender.com" in url, f"URL must target deployed Render service: {url}"

