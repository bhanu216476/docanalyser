"""
Queued document ingestion subsystem.

Public API:
    Models:      IngestionOperation, IngestionJobStatus, IngestionJobRequest,
                 IngestionJob, IngestionJobResponse
    Queue:       IngestionJobQueue
    Service:     IngestionJobService
    Exceptions:  IngestionJobError, IngestionQueueFullError,
                 IngestionJobNotFoundError
"""

from __future__ import annotations

from app.jobs.exceptions import (
    IngestionJobError,
    IngestionJobNotFoundError,
    IngestionQueueFullError,
)
from app.jobs.models import (
    IngestionJob,
    IngestionJobRequest,
    IngestionJobResponse,
    IngestionJobStatus,
    IngestionOperation,
)
from app.jobs.queue import IngestionJobQueue
from app.jobs.service import IngestionJobService

__all__ = [
    # Models
    "IngestionJob",
    "IngestionJobRequest",
    "IngestionJobResponse",
    "IngestionJobStatus",
    "IngestionOperation",
    # Queue / service
    "IngestionJobQueue",
    "IngestionJobService",
    # Exceptions
    "IngestionJobError",
    "IngestionJobNotFoundError",
    "IngestionQueueFullError",
]
