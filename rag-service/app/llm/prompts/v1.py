"""
Prompt V1 — Baseline.

The simplest possible grounded prompt. Serves as the control condition
in prompt experiments. Intentionally minimal so that V2 and V3 improvements
can be isolated and measured against this baseline.

Do not modify this file after experiments have been recorded.
Create a new version if the wording changes materially.
"""

from __future__ import annotations

from app.context.models import BuiltContext
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion

# ---------------------------------------------------------------------------
# V1 system instruction — deliberately concise baseline.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT_V1 = """\
You are a question-answering assistant.

Answer the user's question using only the information provided in the context below.
If the context does not contain the answer, say that the information is not available in the provided sources.
Do not make up facts that are not stated in the context."""


class V1PromptTemplate(BasePromptTemplate):
    """
    Baseline prompt template (V1).

    Structure:
        SYSTEM  → brief grounding instruction
        USER    → raw context followed by the question

    V1 does not enforce explicit citation rules or use structural delimiters
    beyond a simple label. This intentional simplicity is the baseline against
    which V2 and V3 are evaluated.
    """

    @property
    def version(self) -> PromptVersion:
        return PromptVersion.V1

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT_V1

    def build(self, query: str, context: BuiltContext) -> Prompt:
        """
        Assemble V1 prompt.

        User message structure:
            CONTEXT:
            <context_text>

            QUESTION:
            <query>
        """
        citation_ids = self._extract_citation_ids(context)

        if context.context_text.strip():
            user_content = (
                f"CONTEXT:\n{context.context_text}\n\nQUESTION:\n{query}"
            )
        else:
            user_content = (
                "CONTEXT:\nNo relevant context was retrieved.\n\nQUESTION:\n"
                + query
            )

        messages = [
            PromptMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT_V1),
            PromptMessage(role=MessageRole.USER, content=user_content),
        ]

        return Prompt(
            version=self.version,
            system_prompt=_SYSTEM_PROMPT_V1,
            context_text=context.context_text,
            query=query,
            messages=messages,
            citation_ids=citation_ids,
        )
