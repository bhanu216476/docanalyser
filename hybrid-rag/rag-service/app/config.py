"""Application defaults that can be overridden by environment variables."""

import os


DEFAULT_USER_AGENT = "IntelliResearch-RAG/0.1"


def configure_environment() -> None:
    """Set safe defaults without overriding caller-provided environment values."""
    if not os.environ.get("USER_AGENT"):
        os.environ["USER_AGENT"] = DEFAULT_USER_AGENT