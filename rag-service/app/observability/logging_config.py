"""
Structured JSON logging for the DocAnalyser RAG Service.

Injects trace/span IDs into every log record via a logging.Filter,
and configures the root logger to emit JSON lines to stdout.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# OpenTelemetry trace context injection (optional)
# ---------------------------------------------------------------------------
def _get_otel_context() -> tuple[Optional[str], Optional[str]]:
    """Return (trace_id, span_id) hex strings from the active OTel span."""
    try:
        from opentelemetry import trace  # type: ignore[import]
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            trace_id = format(ctx.trace_id, "032x")
            span_id = format(ctx.span_id, "016x")
            return trace_id, span_id
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """
    Formats every log record as a single-line JSON object.

    Fields:
      timestamp   — UTC ISO-8601
      severity    — log level name (DEBUG/INFO/WARN/ERROR/CRITICAL)
      service     — service name from SERVICE_NAME env var or 'rag-service'
      environment — ENVIRONMENT env var or 'development'
      message     — formatted log message
      logger      — logger name
      trace_id    — OTel trace ID (when tracing is active)
      span_id     — OTel span ID
      error_type  — exception class name (on exc_info records)
      stack_trace — abbreviated stack trace (on exc_info records)
    """

    SENSITIVE_PATTERNS = frozenset(
        ["password", "api_key", "secret", "token", "authorization", "bearer"]
    )

    def __init__(self) -> None:
        super().__init__()
        self._service = os.environ.get("SERVICE_NAME", "rag-service")
        self._environment = os.environ.get("ENVIRONMENT", "development")

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        trace_id, span_id = _get_otel_context()

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "severity": record.levelname,
            "service": self._service,
            "environment": self._environment,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if trace_id:
            payload["trace_id"] = trace_id
        if span_id:
            payload["span_id"] = span_id

        # Propagate any extra fields added via LoggerAdapter or extra= kwarg
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _LOG_RECORD_BUILTIN_ATTRS:
                continue
            payload[key] = value

        if record.exc_info:
            exc = record.exc_info[1]
            payload["error_type"] = type(exc).__name__ if exc else None
            payload["stack_trace"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


_LOG_RECORD_BUILTIN_ATTRS = frozenset(
    [
        "args", "created", "exc_info", "exc_text", "filename",
        "funcName", "getMessage", "levelname", "levelno", "lineno",
        "module", "msecs", "message", "msg", "name", "pathname",
        "process", "processName", "relativeCreated", "stack_info",
        "thread", "threadName", "taskName",
    ]
)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure the root logger to emit structured JSON to stdout.

    Respects LOG_LEVEL env var; defaults to INFO.
    Call once during application startup before any other loggers are created.
    """
    level_name = (log_level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
