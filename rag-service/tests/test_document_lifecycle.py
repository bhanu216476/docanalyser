from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.documents import (
    DocumentEvent,
    DocumentLifecycleRequest,
    set_document_lifecycle_service,
)
from app.api.rag import set_pipeline
from app.main import app
from app.pipeline.document_lifecycle import DocumentLifecycleError, DocumentLifecycleService


class FakeVectorStore:
    def __init__(self):
        self.deleted = []

    def delete_by_document_id(self, document_id):
        self.deleted.append(document_id)


class FakeBm25:
    def __init__(self):
        self.removed = []

    def remove_by_document_id(self, document_id):
        self.removed.append(document_id)


class FakePipeline:
    def __init__(self):
        self.vector_store = FakeVectorStore()
        self.bm25_index = FakeBm25()
        self.ingested = []

    def ingest(self, source, document_id=None, metadata=None):
        self.ingested.append((Path(source), document_id, metadata))
        return SimpleNamespace(chunk_count=2)


@pytest.fixture
def fake_service():
    pipeline = FakePipeline()
    service = DocumentLifecycleService(pipeline)
    set_document_lifecycle_service(service)
    yield service, pipeline
    set_document_lifecycle_service(None)
    set_pipeline(None)


def lifecycle_request(event, source=None):
    return DocumentLifecycleRequest(
        event=event,
        document_id="doc-123",
        file_name="research.txt" if source else None,
        source_url=str(source) if source else None,
    )


def test_request_requires_source_for_add():
    with pytest.raises(ValueError, match="source_url is required"):
        lifecycle_request(DocumentEvent.DOCUMENT_ADDED)


@pytest.mark.parametrize("document_id", ["", "   ", "\t"])
def test_api_rejects_blank_document_id(document_id):
    response = TestClient(app).post(
        "/api/v1/documents",
        json={"event": "DOCUMENT_DELETED", "document_id": document_id},
    )

    assert response.status_code == 400


def test_api_accepts_non_blank_document_id():
    request = DocumentLifecycleRequest(event=DocumentEvent.DOCUMENT_DELETED, document_id="doc-123")

    assert request.document_id == "doc-123"


def test_added_event_routes_to_existing_ingestion(fake_service, tmp_path):
    _, pipeline = fake_service
    source = tmp_path / "research.txt"
    source.write_text("content", encoding="utf-8")

    result = DocumentLifecycleService(pipeline).process(lifecycle_request(DocumentEvent.DOCUMENT_ADDED, source))

    assert result["status"] == "PROCESSED"
    assert pipeline.ingested == [(source, "doc-123", {})]
    assert pipeline.vector_store.deleted == ["doc-123"]


def test_updated_event_removes_old_vectors_before_ingestion(fake_service, tmp_path):
    _, pipeline = fake_service
    source = tmp_path / "research.txt"
    source.write_text("updated content", encoding="utf-8")

    DocumentLifecycleService(pipeline).process(lifecycle_request(DocumentEvent.DOCUMENT_UPDATED, source))

    assert pipeline.vector_store.deleted == ["doc-123"]
    assert pipeline.bm25_index.removed == ["doc-123"]
    assert pipeline.ingested == [(source, "doc-123", {})]


def test_added_event_replaces_existing_chunks_on_retry(fake_service, tmp_path):
    _, pipeline = fake_service
    source = tmp_path / "research.txt"
    source.write_text("content", encoding="utf-8")

    DocumentLifecycleService(pipeline).process(lifecycle_request(DocumentEvent.DOCUMENT_ADDED, source))
    DocumentLifecycleService(pipeline).process(lifecycle_request(DocumentEvent.DOCUMENT_ADDED, source))

    assert pipeline.vector_store.deleted == ["doc-123", "doc-123"]


def test_deleted_event_removes_vectors_and_bm25(fake_service):
    _, pipeline = fake_service

    result = DocumentLifecycleService(pipeline).process(lifecycle_request(DocumentEvent.DOCUMENT_DELETED))

    assert result["success"] is True
    assert pipeline.vector_store.deleted == ["doc-123"]
    assert pipeline.bm25_index.removed == ["doc-123"]


def test_api_rejects_unsupported_event():
    client = TestClient(app)
    response = client.post("/api/v1/documents", json={"event": "IGNORED", "document_id": "doc-123"})
    assert response.status_code == 422


def test_api_maps_ingestion_failure_to_500(tmp_path):
    class FailingService:
        def process(self, request):
            raise DocumentLifecycleError("embedding failed")

    set_document_lifecycle_service(FailingService())
    try:
        source = tmp_path / "research.txt"
        source.write_text("content", encoding="utf-8")
        response = TestClient(app).post(
            "/api/v1/documents",
            json={
                "event": "DOCUMENT_ADDED",
                "document_id": "doc-123",
                "file_name": source.name,
                "source_url": str(source),
            },
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "embedding failed"
    finally:
        set_document_lifecycle_service(None)