"""
API integration tests for /api/v1/rag endpoints.

Tests:
    - POST /api/v1/rag/ingest via file upload.
    - POST /api/v1/rag/ingest via file_path parameter.
    - POST /api/v1/rag/ingest with non-existent file returns 404.
    - POST /api/v1/rag/ingest with no arguments returns 400.
    - POST /api/v1/rag/ingest with unsupported extension returns 422.
    - POST /api/v1/rag/query with valid query returns 200 and RAGResponse schema.
    - POST /api/v1/rag/query with empty query returns 422 Unprocessable Entity.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.rag import set_pipeline
from app.main import app
from app.pipeline.demo_cli import generate_demo_pdf
from app.pipeline.rag_pipeline import create_rag_pipeline


@pytest.fixture
def client(tmp_path: Path):
    """Provide a TestClient with an isolated in-memory pipeline injected."""
    test_pipeline = create_rag_pipeline(in_memory=True)
    set_pipeline(test_pipeline)
    with TestClient(app) as test_client:
        yield test_client
    set_pipeline(None)


def test_api_ingest_file_upload_txt(client: TestClient) -> None:
    """Verify ingesting a text file via multipart upload returns 201."""
    content = b"Working hours are 9am to 5pm. Employees get 15 days annual leave."
    response = client.post(
        "/api/v1/rag/ingest",
        files={"file": ("policy.txt", io.BytesIO(content), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["file_name"] == "policy.txt"
    assert data["file_type"] == "txt"
    assert data["chunk_count"] > 0
    assert "total_ms" in data["latency_breakdown_ms"]


def test_api_ingest_file_path(client: TestClient, tmp_path: Path) -> None:
    """Verify ingesting via file_path form field returns 201."""
    f = tmp_path / "handbook.txt"
    f.write_text("Notice period is two months for confirmed staff.", encoding="utf-8")

    response = client.post(
        "/api/v1/rag/ingest",
        data={"file_path": str(f)},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["file_name"] == "handbook.txt"
    assert data["chunk_count"] > 0


def test_api_ingest_missing_file_path_returns_404(client: TestClient) -> None:
    """Verify specifying a non-existent file_path returns 404."""
    response = client.post(
        "/api/v1/rag/ingest",
        data={"file_path": "/nonexistent/path/to/doc.pdf"},
    )
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


def test_api_ingest_no_input_returns_400(client: TestClient) -> None:
    """Verify calling ingest with neither file nor file_path returns 400."""
    response = client.post("/api/v1/rag/ingest")
    assert response.status_code == 400
    assert "Either 'file' (upload) or 'file_path' must be provided." in response.json()["detail"]


def test_api_ingest_unsupported_extension_returns_422(client: TestClient) -> None:
    """Verify unsupported file extension returns 422."""
    response = client.post(
        "/api/v1/rag/ingest",
        files={"file": ("archive.zip", io.BytesIO(b"PK..."), "application/zip")},
    )
    assert response.status_code == 422
    assert "Unsupported document extension" in response.json()["detail"]


def test_api_query_success(client: TestClient) -> None:
    """Verify query endpoint returns 200 and proper RAGResponse structure."""
    # Ingest document first
    client.post(
        "/api/v1/rag/ingest",
        files={"file": ("faq.txt", io.BytesIO(b"Office location is 100 Main St."), "text/plain")},
    )

    response = client.post(
        "/api/v1/rag/query",
        json={"query": "Where is the office located?", "prompt_version": "v2"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Where is the office located?"
    assert "answer" in data
    assert "citations" in data
    assert data["prompt_version"] == "v2"
    assert "latency_breakdown_ms" in data
    assert "total_ms" in data["latency_breakdown_ms"]


def test_api_query_empty_query_returns_422(client: TestClient) -> None:
    """Verify empty query string triggers validation error 422."""
    response = client.post(
        "/api/v1/rag/query",
        json={"query": ""},
    )
    assert response.status_code == 422
