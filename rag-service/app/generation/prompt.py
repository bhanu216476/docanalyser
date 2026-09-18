"""Deterministic prompt construction for evidence-grounded answers."""

from __future__ import annotations

from app.context.models import StructuredContext


class PromptBuilder:
    """Build a prompt that constrains answers to the supplied evidence."""

    def build(self, query: str, context: StructuredContext) -> str:
        evidence_status = (
            "No evidence was retrieved. Do not invent an answer."
            if not context.items
            else "Use only the evidence supplied below."
        )
        return (
            "SYSTEM/INSTRUCTION\n"
            "Answer the user's question using only the supplied evidence.\n"
            "Do not invent facts. Cite supporting claims using the existing [n] "
            "citation markers.\n"
            "If the evidence is insufficient, clearly state that the provided "
            "evidence is insufficient.\n"
            "Do not create or modify citation numbers.\n"
            f"{evidence_status}\n\n"
            "CONTEXT\n"
            f"{context.formatted_text}\n\n"
            "USER QUESTION\n"
            f"{query}"
        )