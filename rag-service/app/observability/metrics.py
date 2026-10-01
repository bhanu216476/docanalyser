"""
Observability module for DocAnalyser RAG Service.

Provides:
  - OpenTelemetry tracer / span context manager
  - Prometheus metrics registry for all RAG-specific metrics
  - Structured JSON logging setup
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from typing_extensions import Self

# ---------------------------------------------------------------------------
# OpenTelemetry setup — graceful no-op when collector is unavailable
# ---------------------------------------------------------------------------
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (  # noqa: F401
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,  # noqa: F401
    )

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Prometheus client — graceful no-op when not installed
# ---------------------------------------------------------------------------
try:
    from prometheus_client import (
        REGISTRY as DEFAULT_REGISTRY,
    )
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------

# Buckets in seconds for latency histograms
_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    float("inf"),
)


class RagMetrics:
    """
    All Prometheus metrics for the RAG platform.

    All instances share the same metrics objects — designed as a singleton
    populated once at application startup.
    """

    _instance: RagMetrics | None = None

    def __new__(cls, registry: Any | None = None) -> Self:
        if registry is not None:
            inst = super().__new__(cls)
            inst._initialized = False
            return inst
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, registry: Any | None = None) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.registry = (
            registry
            if registry is not None
            else (DEFAULT_REGISTRY if _PROMETHEUS_AVAILABLE else None)
        )
        self._setup_metrics(self.registry)

    def _setup_metrics(self, reg: Any | None = None) -> None:
        if not _PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client not available — metrics disabled")
            return

        # HTTP request metrics
        self.http_requests_total = Counter(
            "rag_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=reg,
        )
        self.http_request_duration_seconds = Histogram(
            "rag_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self.http_errors_total = Counter(
            "rag_http_errors_total",
            "Total HTTP error responses (4xx/5xx)",
            ["method", "endpoint", "status_code"],
            registry=reg,
        )

        # Ingestion metrics
        self.ingestion_success_total = Counter(
            "rag_ingestion_success_total",
            "Successfully ingested documents",
            ["file_type"],
            registry=reg,
        )
        self.ingestion_failure_total = Counter(
            "rag_ingestion_failure_total",
            "Failed document ingestion attempts",
            ["file_type", "error_type"],
            registry=reg,
        )

        # Retrieval latency (dense, bm25, hybrid) — separate histograms
        self.retrieval_latency_seconds = Histogram(
            "rag_retrieval_latency_seconds",
            "Retrieval stage latency in seconds",
            ["retrieval_method"],  # dense | bm25 | hybrid | fusion
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self.retrieval_operations_total = Counter(
            "rag_retrieval_operations_total",
            "Total retrieval operations executed",
            ["retrieval_method", "outcome"],  # outcome: success | failure
            registry=reg,
        )

        # Retrieval score distributions (dense/bm25/hybrid scored separately)
        self.retrieval_scores = Histogram(
            "rag_retrieval_scores",
            "Distribution of retrieval relevance scores",
            ["retrieval_method", "score_type"],
            buckets=(
                0.0,
                0.1,
                0.2,
                0.3,
                0.4,
                0.5,
                0.6,
                0.7,
                0.8,
                0.9,
                1.0,
                float("inf"),
            ),
            registry=reg,
        )

        # Reranking latency and candidates
        self.reranking_latency_seconds = Histogram(
            "rag_reranking_latency_seconds",
            "Reranking stage latency in seconds",
            ["reranker_type"],
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self.reranking_candidates_processed = Histogram(
            "rag_reranking_candidates_processed",
            "Number of candidates processed per reranking call",
            ["reranker_type"],
            buckets=(1, 5, 10, 20, 50, 100, float("inf")),
            registry=reg,
        )

        # LLM latency and failures
        self.llm_request_duration_seconds = Histogram(
            "rag_llm_request_duration_seconds",
            "LLM generation request duration in seconds",
            ["provider", "model", "is_mock"],  # is_mock: true | false
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self.llm_requests_total = Counter(
            "rag_llm_requests_total",
            "Total LLM generation requests",
            ["provider", "model", "outcome"],  # outcome: success | failure
            registry=reg,
        )
        self.llm_failures_total = Counter(
            "rag_llm_failures_total",
            "Total LLM generation failures",
            ["provider", "error_type"],
            registry=reg,
        )

        # Token usage — input/output/total separately
        self.llm_tokens_total = Counter(
            "rag_llm_tokens_total",
            "Total tokens consumed by LLM (prompt + completion)",
            ["token_type", "provider", "model"],  # token_type: input | output
            registry=reg,
        )

        # Pipeline-level metrics
        self.rag_pipeline_duration_seconds = Histogram(
            "rag_pipeline_duration_seconds",
            "Total end-to-end RAG query pipeline duration in seconds",
            ["outcome"],  # success | failure
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self.rag_pipeline_failures_total = Counter(
            "rag_pipeline_failures_total",
            "Total RAG query pipeline failures",
            ["stage"],  # retrieval | reranking | context | llm | citation | pipeline
            registry=reg,
        )

        # No-answer rate
        self.rag_queries_total = Counter(
            "rag_queries_completed_total",
            "Total completed RAG queries (successful pipeline, regardless of answer)",
            [],
            registry=reg,
        )
        self.rag_no_answer_total = Counter(
            "rag_no_answer_total",
            "Completed queries that returned a no-answer response",
            [],
            registry=reg,
        )
        self.rag_no_answer_rate = Gauge(
            "rag_no_answer_rate",
            "Rate of no-answer responses over all completed queries (sliding estimate)",
            registry=reg,
        )

        # Citation failure rate
        self.citation_verifications_total = Counter(
            "rag_citation_verifications_total",
            "Total citation verifications performed",
            ["outcome"],  # passed | failed | unsupported | missing | unavailable
            registry=reg,
        )
        self.citation_failure_rate = Gauge(
            "rag_citation_failure_rate",
            "Rate of citation verification failures over all verifications (sliding estimate)",
            registry=reg,
        )
        self.citation_failures_total = Counter(
            "rag_citation_failures_total",
            "Citation verification failures (failed + unsupported + missing)",
            ["failure_type"],
            registry=reg,
        )

        logger.info("RAG Prometheus metrics registered")

    # ------------------------------------------------------------------
    # Helper recording methods
    # ------------------------------------------------------------------

    def record_retrieval_latency(
        self,
        duration_s: float,
        method: str,
        outcome: str = "success",
    ) -> None:
        """Record retrieval stage latency and outcome counter."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.retrieval_latency_seconds.labels(retrieval_method=method).observe(
            duration_s
        )
        self.retrieval_operations_total.labels(
            retrieval_method=method, outcome=outcome
        ).inc()

    def record_retrieval_scores(
        self,
        scores: list[float],
        method: str,
        score_type: str = "relevance",
    ) -> None:
        """Record distribution of retrieval relevance scores."""
        if not _PROMETHEUS_AVAILABLE or not scores:
            return
        for score in scores:
            self.retrieval_scores.labels(
                retrieval_method=method, score_type=score_type
            ).observe(score)

    def record_reranking(
        self,
        duration_s: float,
        candidate_count: int,
        reranker_type: str = "default",
    ) -> None:
        """Record reranking latency and candidate count."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.reranking_latency_seconds.labels(reranker_type=reranker_type).observe(
            duration_s
        )
        self.reranking_candidates_processed.labels(reranker_type=reranker_type).observe(
            candidate_count
        )

    def record_llm_request(
        self,
        duration_s: float,
        provider: str,
        model: str,
        is_mock: bool,
        outcome: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_type: str | None = None,
    ) -> None:
        """Record LLM generation request metrics including token usage."""
        if not _PROMETHEUS_AVAILABLE:
            return
        is_mock_label = "true" if is_mock else "false"
        self.llm_request_duration_seconds.labels(
            provider=provider, model=model, is_mock=is_mock_label
        ).observe(duration_s)
        self.llm_requests_total.labels(
            provider=provider, model=model, outcome=outcome
        ).inc()
        if outcome == "failure" and error_type:
            self.llm_failures_total.labels(
                provider=provider, error_type=error_type
            ).inc()
        if input_tokens is not None:
            self.llm_tokens_total.labels(
                token_type="input", provider=provider, model=model
            ).inc(input_tokens)
        if output_tokens is not None:
            self.llm_tokens_total.labels(
                token_type="output", provider=provider, model=model
            ).inc(output_tokens)

    def record_ingestion_success(self, file_type: str) -> None:
        """Record successful document ingestion."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.ingestion_success_total.labels(file_type=file_type).inc()

    def record_ingestion_failure(
        self, file_type: str, error_type: str = "UnknownError"
    ) -> None:
        """Record failed document ingestion."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.ingestion_failure_total.labels(
            file_type=file_type, error_type=error_type
        ).inc()

    def record_pipeline_duration(
        self, duration_s: float, outcome: str = "success"
    ) -> None:
        """Record end-to-end RAG pipeline duration."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.rag_pipeline_duration_seconds.labels(outcome=outcome).observe(duration_s)

    def record_pipeline_failure(self, stage: str) -> None:
        """Record a pipeline stage failure."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.rag_pipeline_failures_total.labels(stage=stage).inc()

    def record_no_answer(
        self,
        is_no_answer: bool,
        completed_count: int | None = None,
        no_answer_count: int | None = None,
    ) -> None:
        """Record a completed query and update no-answer metrics and gauge."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self.rag_queries_total.inc()
        if is_no_answer:
            self.rag_no_answer_total.inc()
        if completed_count is not None and no_answer_count is not None:
            rate = no_answer_count / completed_count if completed_count > 0 else 0.0
            self.rag_no_answer_rate.set(rate)
        else:
            try:
                tot = self.rag_queries_total._value.get()
                no_ans = self.rag_no_answer_total._value.get()
                rate = no_ans / tot if tot > 0 else 0.0
                self.rag_no_answer_rate.set(rate)
            except Exception:  # noqa: BLE001, S110
                pass

    def record_citation_verification(
        self,
        overall_status: str,
        failed_count: int | None = None,
        total_verifications: int | None = None,
    ) -> None:
        """Record citation verification outcome and update failure rate gauge."""
        if not _PROMETHEUS_AVAILABLE:
            return
        # Map VerificationResult.overall_status values to labels
        outcome_map = {
            "passed": "passed",
            "failed": "failed",
            "unsupported": "unsupported",
            "missing": "missing",
            "unavailable": "unavailable",
            "no_citations": "passed",
        }
        outcome = outcome_map.get(overall_status, "failed")
        self.citation_verifications_total.labels(outcome=outcome).inc()
        if outcome in ("failed", "unsupported", "missing"):
            self.citation_failures_total.labels(failure_type=outcome).inc()
        if total_verifications is not None and failed_count is not None:
            rate = (
                failed_count / total_verifications if total_verifications > 0 else 0.0
            )
            self.citation_failure_rate.set(rate)
        else:
            self._total_citations = getattr(self, "_total_citations", 0) + 1
            if outcome in ("failed", "unsupported", "missing"):
                self._failed_citations = getattr(self, "_failed_citations", 0) + 1
            rate = (
                getattr(self, "_failed_citations", 0) / self._total_citations
                if self._total_citations > 0
                else 0.0
            )
            self.citation_failure_rate.set(rate)


# Module-level singleton
rag_metrics = RagMetrics()


# ---------------------------------------------------------------------------
# OpenTelemetry tracer
# ---------------------------------------------------------------------------


def setup_tracing(
    service_name: str = "rag-service",
    otlp_endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> None:
    """
    Configure the OpenTelemetry SDK tracer provider with OTLP export.

    Designed to be called once at application startup. Falls back to a
    no-op tracer if the SDK is unavailable or the collector is unreachable.
    The application continues to run even if tracing setup fails.
    """
    if not _OTEL_AVAILABLE:
        logger.warning("opentelemetry-sdk not available — tracing disabled")
        return

    try:
        endpoint = otlp_endpoint or os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
        )
        traces_endpoint = endpoint.rstrip("/") + "/v1/traces"

        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Sampling: head-based with configurable probability
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        sampler = ParentBased(root=TraceIdRatioBased(sample_rate))

        provider = TracerProvider(resource=resource, sampler=sampler)

        # OTLP exporter — non-blocking batch
        otlp_exporter = OTLPSpanExporter(endpoint=traces_endpoint, timeout=5)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        trace.set_tracer_provider(provider)
        logger.info(
            "OpenTelemetry tracing configured: service=%s endpoint=%s sample_rate=%s",
            service_name,
            traces_endpoint,
            sample_rate,
        )
    except Exception as exc:  # noqa: BLE001  # pragma: no cover  # noqa: BLE001
        logger.warning(
            "OpenTelemetry tracing setup failed (%s) — continuing without tracing", exc
        )


def get_tracer(name: str = "rag-service") -> Any:
    """Return an OpenTelemetry tracer. No-op if SDK is unavailable."""
    if not _OTEL_AVAILABLE:
        return _NoOpTracer()
    return trace.get_tracer(name)


class _NoOpTracer:
    """Minimal no-op tracer used when opentelemetry-sdk is not installed."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Generator:  # type: ignore[misc]
        yield _NoOpSpan()


class _NoOpSpan:
    """Minimal no-op span."""

    def set_attribute(self, *_: Any, **__: Any) -> None:
        pass

    def record_exception(self, *_: Any, **__: Any) -> None:
        pass

    def set_status(self, *_: Any, **__: Any) -> None:
        pass


tracer = get_tracer("rag-service")
