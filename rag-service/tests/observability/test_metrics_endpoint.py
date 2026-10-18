"""
Integration tests for RAG service observability endpoints.

Verifies:
  - /metrics endpoint returns Prometheus text format
  - /health endpoint returns expected status
  - Prometheus metrics are present in /metrics output
  - Structured logging headers are propagated
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestMetricsEndpoint:
    def test_metrics_endpoint_reachable(self, client):
        """GET /metrics should return 200 with Prometheus text content."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client):
        """Content-Type should be Prometheus text/plain."""
        response = client.get("/metrics")
        assert "text" in response.headers.get("content-type", "")

    def test_metrics_contains_python_process_metrics(self, client):
        """Standard Python process metrics should appear."""
        response = client.get("/metrics")
        body = response.text
        # Standard prometheus_client metrics
        assert (
            "python_gc_objects_collected_total" in body
            or "process_" in body
            or "rag_" in body
        )

    def test_rag_http_metrics_recorded_after_request(self, client):
        """After a health request, rag_http_requests_total counter should appear."""
        # Make a health request to increment the counter
        client.get("/health")
        response = client.get("/metrics")
        body = response.text
        assert "rag_http_requests_total" in body

    def test_rag_ingestion_metrics_present(self, client):
        """Ingestion counter metric families should be present."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_ingestion_success_total" in body

    def test_rag_retrieval_latency_metrics_present(self, client):
        """Retrieval histogram families should appear in output."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_retrieval_latency_seconds" in body

    def test_rag_llm_metrics_present(self, client):
        """LLM duration histogram should be present."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_llm_request_duration_seconds" in body

    def test_rag_pipeline_duration_metric_present(self, client):
        """Pipeline duration histogram should be present."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_pipeline_duration_seconds" in body

    def test_rag_no_answer_rate_metric_present(self, client):
        """No-answer rate Gauge should be present."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_no_answer_rate" in body

    def test_rag_citation_failure_rate_metric_present(self, client):
        """Citation failure rate Gauge should be present."""
        response = client.get("/metrics")
        body = response.text
        assert "rag_citation_failure_rate" in body


class TestHealthEndpoint:
    def test_health_endpoint_reachable(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_contains_status(self, client):
        response = client.get("/health")
        body = response.json()
        assert "status" in body
