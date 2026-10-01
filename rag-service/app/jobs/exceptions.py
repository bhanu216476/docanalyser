"""
Exceptions raised by the queued ingestion subsystem.

Hierarchy:
    IngestionJobError
        ├── IngestionQueueFullError      → queue capacity reached
        └── IngestionJobNotFoundError    → unknown job identifier

Job execution failures (loader / embedding / vector-store / BM25 errors)
are NOT raised to the caller: they are captured on the job record itself
(``status=FAILED``, ``error``, ``error_type``) so a single failing job can
never terminate the background worker.
"""

from __future__ import annotations


class IngestionJobError(Exception):
    """Base exception for queued ingestion errors."""


class IngestionQueueFullError(IngestionJobError):
    """Raised when the ingestion queue has reached its configured capacity."""


class IngestionJobNotFoundError(IngestionJobError):
    """Raised when a job identifier does not correspond to a known job."""
