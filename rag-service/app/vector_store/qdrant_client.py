"""
Qdrant client factory and connection management.

Provides a clean factory for instantiating official QdrantClient instances,
supporting remote HTTP connections, API key authentication, custom timeouts,
and in-memory test clients (:memory:).
"""

from __future__ import annotations

import logging
from typing import Optional

from qdrant_client import QdrantClient

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_qdrant_client(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    location: Optional[str] = None,
) -> QdrantClient:
    """
    Instantiate a configured QdrantClient.

    Args:
        url: Remote Qdrant server URL (e.g. 'http://localhost:6333').
             Defaults to ``settings.qdrant_url``.
        api_key: Optional Qdrant API key for authentication.
                 Defaults to ``settings.qdrant_api_key``.
        timeout: Request timeout in seconds. Defaults to ``settings.qdrant_timeout``.
        location: Special location override (e.g. ':memory:' for in-memory testing).

    Returns:
        Configured ``QdrantClient`` instance.
    """
    # Special in-memory mode for automated testing without Docker
    if location == ":memory:" or url == ":memory:":
        logger.info("Initializing in-memory Qdrant client (:memory:)")
        return QdrantClient(":memory:")

    resolved_url = url or settings.qdrant_url
    resolved_api_key = api_key if api_key is not None else (settings.qdrant_api_key or None)
    resolved_timeout = timeout if timeout is not None else settings.qdrant_timeout

    logger.info(
        "Connecting to Qdrant at %s (timeout=%.1fs, auth=%s)",
        resolved_url,
        resolved_timeout,
        "ENABLED" if resolved_api_key else "DISABLED",
    )

    return QdrantClient(
        url=resolved_url,
        api_key=resolved_api_key or None,
        timeout=resolved_timeout,
    )
