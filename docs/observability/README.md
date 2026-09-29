# DocAnalyser Observability Architecture & Operations Guide

## 1. Overview

DocAnalyser implements end-to-end distributed observability across its microservice architecture using:
- **Distributed Tracing**: OpenTelemetry (OTel) SDK in Python and Micrometer Tracing (OTel Bridge) in Spring Boot, reporting to an OpenTelemetry Collector.
- **Metrics Collection**: Prometheus scraping Spring Boot Actuator (`/actuator/prometheus`), FastAPI Prometheus client (`/metrics`), and OTel Collector internals (`/metrics`).
- **Visualization & Dashboards**: Grafana pre-provisioned with Prometheus datasource and comprehensive platform & RAG performance dashboards.
- **Structured Logging**: Unified JSON logging format across Spring Boot (Logstash Logback Encoder) and Python (custom `JsonFormatter`) with contextual correlation IDs (`trace_id`, `span_id`, `requestId` / `request_id`, `operation_name`, `duration_ms`).

```
                ┌──────────────────────────────────────────────┐
                │             End-User / Client               │
                └──────────────────────┬───────────────────────┘
                                       │ HTTP + X-Request-Id
                                       ▼
                 ┌───────────────────────────────────────────┐
                 │       Spring Boot Service (:8080)         │
                 │   - RequestLoggingFilter (MDC trace inject)│
                 │   - Micrometer Tracing (OTel Bridge)      │
                 │   - /actuator/prometheus                  │
                 └─────────────┬─────────────────────────────┘
                               │ HTTP /api/v1/rag/*
                               ▼
                 ┌───────────────────────────────────────────┐
                 │        Python RAG Service (:8000)         │
                 │   - FastAPI OTel Instrumentation          │
                 │   - Prometheus Middleware & /metrics       │
                 │   - Custom RagMetrics (SLIs & RAG stages) │
                 └─────────────┬─────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │ Traces (OTLP HTTP :4318)      │ Metrics Scraping (:15s)
               ▼                               ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│  OTel Collector (:4317/4318)│  │     Prometheus (:9090)      │
│  - Batch processor          │  │  - docanalyser-backend      │
│  - Trace pipeline & export  │  │  - docanalyser-rag-service  │
└─────────────────────────────┘  │  - otel-collector           │
                                 └──────────────┬──────────────┘
                                                │
                                                ▼
                                 ┌─────────────────────────────┐
                                 │      Grafana (:3001)        │
                                 │  - Platform Overview        │
                                 │  - RAG Performance          │
                                 └─────────────────────────────┘
```

---

## 2. Distributed Tracing

### Spring Boot Service
- **Instrumentation**: `micrometer-tracing-bridge-otel` paired with `opentelemetry-exporter-otlp`.
- **Trace Propagation**: Standard W3C TraceContext headers (`traceparent`, `tracestate`) propagated automatically across inter-service HTTP requests.
- **Endpoint**: Configured in `application.yml` via `management.otlp.tracing.endpoint` (`http://otel-collector:4318/v1/traces` in Docker).
- **Sampling Probability**: Defaulted to `1.0` (100%) in development and configurable via `MANAGEMENT_TRACING_SAMPLING_PROBABILITY`.

### Python RAG Service
- **Instrumentation**: `opentelemetry-instrumentation-fastapi` automatically instruments incoming HTTP requests, creating root spans and propagating trace context.
- **Exporter**: `OTLPSpanExporter` communicating with the OTel Collector via HTTP proto (`http://otel-collector:4318/v1/traces`).
- **Resilience**: Graceful fallback to `_NoOpTracer` if OTel SDK or collector is unavailable — pipeline execution never blocks on observability failures.
- **Granular Spans**: Explicit spans for `rag.ingest` and `rag.pipeline` capturing pipeline execution attributes (`rag.prompt_version`, `rag.chunk_count`, `rag.file_type`).

---

## 3. Metrics & Monitoring (Prometheus)

Prometheus scrapes targets every 15 seconds as defined in `infrastructure/prometheus.yml`:

| Target | Scrape Path | Port | Protocol | Description |
|---|---|---|---|---|
| `backend` | `/actuator/prometheus` | 8080 | HTTP | JVM memory, GC pauses, Spring HTTP requests, HikariCP pool stats |
| `rag-service` | `/metrics` | 8000 | HTTP | Process CPU/memory, HTTP latency, RAG-specific domain metrics |
| `otel-collector` | `/metrics` | 8888 | HTTP | Collector batch queue, receivers, exporter dropped spans |

### RAG Domain Metrics (`RagMetrics`)

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `rag_http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP requests handled |
| `rag_http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request duration distribution |
| `rag_http_errors_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP errors (4xx / 5xx) |
| `rag_ingestion_success_total` | Counter | `file_type` | Successfully ingested documents |
| `rag_ingestion_failure_total` | Counter | `file_type`, `error_type` | Failed document ingestion attempts |
| `rag_retrieval_latency_seconds` | Histogram | `retrieval_method` (`dense`, `bm25`, `fusion`) | Latency by retrieval strategy |
| `rag_retrieval_operations_total` | Counter | `retrieval_method`, `outcome` | Execution counts by retrieval method |
| `rag_retrieval_scores` | Histogram | `retrieval_method`, `score_type` | Relevance score distributions |
| `rag_reranking_latency_seconds` | Histogram | `reranker_type` | Candidate reranker latency |
| `rag_reranking_candidates_processed` | Histogram | `reranker_type` | Count of candidates reranked per query |
| `rag_llm_request_duration_seconds` | Histogram | `provider`, `model`, `is_mock` | Generation latency per model |
| `rag_llm_requests_total` | Counter | `provider`, `model`, `outcome` | Total LLM requests |
| `rag_llm_failures_total` | Counter | `provider`, `error_type` | Total LLM generation failures |
| `rag_llm_tokens_total` | Counter | `token_type` (`input`, `output`), `provider`, `model` | Exact token consumption |
| `rag_pipeline_duration_seconds` | Histogram | `outcome` (`success`, `failure`) | End-to-end RAG query latency |
| `rag_pipeline_failures_total` | Counter | `stage` (`retrieval`, `reranking`, `context`, `llm`) | Failures categorized by pipeline stage |
| `rag_queries_completed_total` | Counter | (none) | Total queries processed successfully |
| `rag_no_answer_total` | Counter | (none) | Queries yielding no answer / refusal |
| `rag_no_answer_rate` | Gauge | (none) | Dynamic ratio of no-answer responses |
| `rag_citation_verifications_total` | Counter | `outcome` (`passed`, `failed`, `unsupported`, etc.) | Verification outcome counts |
| `rag_citation_failures_total` | Counter | `failure_type` | Citation failures |
| `rag_citation_failure_rate` | Gauge | (none) | Dynamic citation verification failure rate |

---

## 4. Grafana Dashboards

Dashboards are automatically provisioned at startup from `infrastructure/grafana/`:

1. **DocAnalyser - Platform Overview (`docanalyser-platform-overview`)**:
   - HTTP Request Rate (Spring Boot + FastAPI)
   - HTTP Error Rate (4xx / 5xx)
   - Spring Boot HTTP Latency (p50, p95, p99)
   - FastAPI HTTP Latency (p50, p95, p99)
   - JVM Memory & Garbage Collection Pause Times
   - Document Ingestion Rate & Failures by File Type

2. **DocAnalyser - RAG Performance (`docanalyser-rag-performance`)**:
   - End-to-End RAG Query Latency (p50, p95, p99)
   - Stage-by-Stage Latency Breakdown (Retrieval, Reranking, LLM)
   - Retrieval Score Distributions
   - LLM Token Usage (Input vs. Output Tokens per second)
   - Real-time No-Answer Rate Gauge & Thresholds
   - Real-time Citation Verification Failure Rate Gauge & Thresholds
   - Citation Outcomes & Verification Status

---

## 5. Structured JSON Logging

Logs are formatted as single-line JSON objects with UTC timestamps and standard fields.

### Common JSON Fields
- `timestamp`: ISO-8601 UTC timestamp
- `severity` / `level`: Log level (`INFO`, `WARN`, `ERROR`, `DEBUG`)
- `service_name` / `service`: Originating service (`spring-boot-service` or `rag-service`)
- `environment`: Runtime environment (`development`, `staging`, `production`)
- `message`: Sanitized log message
- `logger` / `logger_name`: Originating logger class or module
- `trace_id` / `traceId`: OpenTelemetry 32-hex trace identifier
- `span_id` / `spanId`: OpenTelemetry 16-hex span identifier
- `request_id` / `requestId`: Request correlation ID propagated via `X-Request-Id`
- `duration_ms`: Duration of HTTP operation in milliseconds (when applicable)
- `error_type`: Exception class name on error records
- `stack_trace`: Formatted exception stack trace (error level only)

---

## 6. Local Operations & Verification

### Prerequisites
- Docker & Docker Compose
- JDK 21+ and Maven Wrapper (`mvnw`)
- Python 3.10+ virtual environment

### Starting the Platform
From the repository root:
```bash
docker compose up -d --build
```

### Accessing Endpoints

| Service | URL | Credentials / Notes |
|---|---|---|
| **Grafana** | `http://localhost:3001` | User: `admin`, Password: `${GRAFANA_PASSWORD:-changeme}` |
| **Prometheus** | `http://localhost:9090` | Open UI, queries & targets status |
| **Spring Boot Actuator** | `http://localhost:8080/actuator/prometheus` | Prometheus text metric stream |
| **Python Metrics** | `http://localhost:8000/metrics` | Prometheus text metric stream |
| **OTel Collector HTTP** | `http://localhost:4318` | OTLP HTTP receiver endpoint |
| **OTel Collector gRPC** | `http://localhost:4317` | OTLP gRPC receiver endpoint |

### Running Automated Test Suites

**Spring Boot Observability Tests:**
```bash
cd backend/spring-boot-service
./mvnw test -Dtest=ActuatorObservabilityTest
```

**Python Observability Tests:**
```bash
cd rag-service
.\.venv\Scripts\pytest tests/observability/ -v
```
