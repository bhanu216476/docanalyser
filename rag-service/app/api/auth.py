"""
Internal API authentication dependency for FastAPI routes.

Validates the X-Internal-Token header (or Bearer Authorization token)
against the configured N8N_INGESTION_TOKEN.

If no token is configured (e.g. in development or testing), authentication
is gracefully bypassed to preserve 100% backward compatibility.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def verify_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> bool:
    """
    Authenticate an internal request via X-Internal-Token or Authorization: Bearer.

    Returns:
        True if authentication succeeds or internal token verification is unconfigured.

    Raises:
        HTTPException 401: If an internal token is configured and the caller fails to provide it.
    """
    expected = settings.n8n_ingestion_token.strip()
    if not expected:
        # Backward-compatible: If no token configured in environment, allow call
        return True

    provided = x_internal_token
    if not provided and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1]

    if not provided or not hmac.compare_digest(provided.strip(), expected):
        logger.warning("Unauthorized internal request: invalid or missing X-Internal-Token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal authentication token (X-Internal-Token header required)",
        )

    return True
