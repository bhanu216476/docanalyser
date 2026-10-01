"""
DocAnalyser RAG Service — FastAPI entry point.

Wires up:
  - Structured JSON logging
  - OpenTelemetry distributed tracing
  - Prometheus /metrics endpoint
  - FastAPI OTel instrumentation middleware
  - API routers: health, retrieval, rag, documents
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Setup structured logging first (before any imports that log)
from app.observability.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

# Setup OpenTelemetry tracing
from app.observability.metrics import rag_metrics, setup_tracing

_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
_sample_rate = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
setup_tracing(
    service_name=os.environ.get("SERVICE_NAME", "rag-service"),
    otlp_endpoint=_otel_endpoint,
    sample_rate=_sample_rate,
)

# Instrument FastAPI with OpenTelemetry (no-op if SDK unavailable)
try:
    from opentelemetry.instrumentation.fastapi import (
        FastAPIInstrumentor,  # type: ignore[import]
    )

    _FASTAPI_INSTRUMENTOR_AVAILABLE = True
except ImportError:
    _FASTAPI_INSTRUMENTOR_AVAILABLE = False

from app.api import documents, health, jobs, rag, retrieval  # noqa: E402

app = FastAPI(
    title="DocAnalyser RAG Service",
    description="Python RAG Service for document processing and retrieval",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Prometheus metrics middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next: Any) -> Response:
    """Record per-request Prometheus HTTP metrics and duration."""
    start = time.perf_counter()

    # Normalise endpoint label (avoid cardinality explosion — strip path params)
    path = request.url.path
    method = request.method

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        duration = time.perf_counter() - start
        rag_metrics.http_requests_total.labels(
            method=method, endpoint=path, status_code=str(status_code)
        ).inc()
        rag_metrics.http_errors_total.labels(
            method=method, endpoint=path, status_code=str(status_code)
        ).inc()
        rag_metrics.http_request_duration_seconds.labels(
            method=method, endpoint=path
        ).observe(duration)
        raise

    duration = time.perf_counter() - start
    status_str = str(status_code)

    rag_metrics.http_requests_total.labels(
        method=method, endpoint=path, status_code=status_str
    ).inc()
    rag_metrics.http_request_duration_seconds.labels(
        method=method, endpoint=path
    ).observe(duration)
    if status_code >= 400:
        rag_metrics.http_errors_total.labels(
            method=method, endpoint=path, status_code=status_str
        ).inc()

    return response


# ---------------------------------------------------------------------------
# Prometheus /metrics scrape endpoint
# ---------------------------------------------------------------------------
@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics in text format."""
    try:
        from prometheus_client import (  # type: ignore[import]
            CONTENT_TYPE_LATEST,
            generate_latest,
        )

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return Response(
            content="# prometheus_client not available\n", media_type="text/plain"
        )


# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(retrieval.router)
app.include_router(rag.router)
app.include_router(documents.router)
app.include_router(jobs.router)


@app.exception_handler(RequestValidationError)
async def lifecycle_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        serializable_error = dict(error)
        if "ctx" in serializable_error:
            serializable_error["ctx"] = {
                key: str(value) for key, value in serializable_error["ctx"].items()
            }
        errors.append(serializable_error)
    status_code = 422
    if request.url.path == "/api/v1/documents" and any(
        error.get("loc", ())[-1:] == ("document_id",)
        and isinstance(error.get("input"), str)
        and not error["input"].strip()
        for error in errors
    ):
        status_code = 400
    return JSONResponse(status_code=status_code, content={"detail": errors})


# ---------------------------------------------------------------------------
# Instrument FastAPI with OpenTelemetry (after routes are registered)
# ---------------------------------------------------------------------------
if _FASTAPI_INSTRUMENTOR_AVAILABLE:
    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="metrics,health",
        )
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except Exception as exc:  # noqa: BLE001  # noqa: BLE001
        logger.warning("FastAPI OTel instrumentation failed: %s", exc)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info(
        "RAG Service starting",
        extra={
            "service": "rag-service",
            "environment": os.environ.get("ENVIRONMENT", "development"),
        },
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    # Release the queued-ingestion worker if one was started. This does not
    # create a job service (and therefore no RAG pipeline) when unused.
    await jobs.stop_worker_if_running()
    logger.info("RAG Service shutting down")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
