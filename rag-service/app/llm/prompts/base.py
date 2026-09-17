"""
Base prompt template abstraction.

All prompt version templates must implement BasePromptTemplate,
which provides a consistent interface for the PromptBuilder registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.context.models import BuiltContext
from app.llm.prompts.models import Prompt, PromptVersion


class BasePromptTemplate(ABC):
    """
    Abstract base class for versioned prompt templates.

    Each concrete subclass encapsulates the system prompt text and the
    assembly logic for a single prompt version. This keeps all prompt
    wording within version-specific files rather than scattered across
    the application.

    Subclasses must be immutable — once registered in the PromptBuilder
    registry, a version's wording must not change without creating a new
    version class.
    """

    @property
    @abstractmethod
    def version(self) -> PromptVersion:
        """Return the PromptVersion this template implements."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        Return the system instruction string for this prompt version.

        The system prompt must be:
        - Concise and unambiguous.
        - Provider-independent (no vendor-specific syntax).
        - Safe for multi-turn re-use without modification.
        """
        ...

    @abstractmethod
    def build(self, query: str, context: BuiltContext) -> Prompt:
        """
        Assemble the final Prompt from a user query and a BuiltContext.

        Responsibilities:
        - Wrap context_text in appropriate delimiters for this version.
        - Compose the messages list.
        - Preserve context integrity — do not modify evidence text.
        - Preserve citation IDs exactly as supplied.

        Args:
            query:   The raw user question string.
            context: The BuiltContext from the Context Builder.

        Returns:
            A frozen Prompt instance.
        """
        ...

    def _extract_citation_ids(self, context: BuiltContext) -> list[str]:
        """
        Extract citation IDs from the BuiltContext citations list.

        Uses the typed Citation objects rather than parsing the raw
        context_text string, avoiding any risk of text-parse bugs.
        """
        return [c.citation_id for c in context.citations]
