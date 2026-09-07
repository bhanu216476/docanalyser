"""
Tests for FastAPI application health check endpoint.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify that GET /health returns HTTP 200 with status UP."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}
