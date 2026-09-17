"""
PromptBuilder — central registry for assembling versioned prompts.

The PromptBuilder owns the mapping from PromptVersion → BasePromptTemplate
and provides a single entry point for prompt assembly. No if/else version
chains exist outside this module.

Usage:
    builder = PromptBuilder()
    prompt = builder.build(query="How many leave days?", context=built_context)
    prompt = builder.build(query=..., context=..., version="v3")
"""

from __future__ import annotations

import logging
from typing import Union

from app.context.models import BuiltContext
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.models import Prompt, PromptVersion
from app.llm.prompts.v1 import V1PromptTemplate
from app.llm.prompts.v2 import V2PromptTemplate
from app.llm.prompts.v3 import V3PromptTemplate

logger = logging.getLogger(__name__)


class UnknownPromptVersionError(ValueError):
    """Raised when a requested prompt version is not registered."""


# ---------------------------------------------------------------------------
# Version registry — add new versions here. One entry per version.
# ---------------------------------------------------------------------------
_DEFAULT_REGISTRY: dict[PromptVersion, BasePromptTemplate] = {
    PromptVersion.V1: V1PromptTemplate(),
    PromptVersion.V2: V2PromptTemplate(),
    PromptVersion.V3: V3PromptTemplate(),
}


class PromptBuilder:
    """
    Assembles versioned, structured prompts from a user query and BuiltContext.

    The builder delegates to version-specific BasePromptTemplate subclasses
    registered at construction time. A custom registry can be injected for
    testing or extension.

    Args:
        registry: Optional mapping of PromptVersion to template instances.
                  Defaults to the standard V1/V2/V3 registry.
        default_version: Version to use when none is specified in build().
                         Defaults to V2 (production-grade grounding).
    """

    def __init__(
        self,
        registry: dict[PromptVersion, BasePromptTemplate] | None = None,
        default_version: PromptVersion | str = PromptVersion.V2,
    ) -> None:
        self._registry: dict[PromptVersion, BasePromptTemplate] = (
            registry if registry is not None else dict(_DEFAULT_REGISTRY)
        )
        self._default_version: PromptVersion = (
            PromptVersion.from_string(default_version)
            if isinstance(default_version, str)
            else default_version
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        query: str,
        context: BuiltContext,
        version: Union[PromptVersion, str, None] = None,
    ) -> Prompt:
        """
        Assemble a Prompt for the given query and context.

        Args:
            query:   User question string (not modified).
            context: BuiltContext from the Context Builder (not modified).
            version: Prompt version to use. Accepts a PromptVersion enum
                     member or a version string ('v1', 'v2', 'v3').
                     Defaults to the builder's default_version.

        Returns:
            A frozen Prompt instance.

        Raises:
            UnknownPromptVersionError: If the requested version is not registered.
            ValueError: If query is blank.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")

        resolved_version = self._resolve_version(version)
        template = self._registry.get(resolved_version)

        if template is None:
            registered = ", ".join(v.value for v in self._registry)
            raise UnknownPromptVersionError(
                f"Prompt version '{resolved_version.value}' is not registered. "
                f"Registered versions: {registered}."
            )

        logger.debug(
            "Building prompt: version=%s, query_len=%d, context_tokens=%d",
            resolved_version.value,
            len(query),
            context.token_count,
        )

        return template.build(query=query, context=context)

    def registered_versions(self) -> list[PromptVersion]:
        """Return a sorted list of all registered prompt versions."""
        return sorted(self._registry.keys(), key=lambda v: v.value)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_version(
        self,
        version: Union[PromptVersion, str, None],
    ) -> PromptVersion:
        """Resolve a version argument to a PromptVersion enum member."""
        if version is None:
            return self._default_version
        if isinstance(version, PromptVersion):
            return version
        try:
            return PromptVersion.from_string(version)
        except ValueError as exc:
            raise UnknownPromptVersionError(str(exc)) from exc
