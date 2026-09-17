"""
Prompt V2 — Grounded with Citation Requirements.

Builds on V1 by adding:
- Explicit grounding rule (use only supplied context).
- Citation requirement (cite claims using supplied IDs only).
- No-answer instruction (do not guess when evidence is insufficient).
- Structural delimiters (<context> and <question> tags) to clearly
  separate system instructions from retrieved content and user input.
- Citation integrity rule (never invent IDs not present in context).

Do not modify this file after experiments have been recorded.
Create a new version if the wording changes materially.
"""

from __future__ import annotations

from app.context.models import BuiltContext
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion

# ---------------------------------------------------------------------------
# V2 system instruction — grounding + citation + no-answer.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT_V2 = """\
You are a grounded question-answering assistant.

Your answer must be based exclusively on the evidence provided inside the \
<context> tags below. Do not draw on outside knowledge.

Citation rules:
- Each evidence block is tagged with a citation ID such as [1], [2], [3].
- When you state a fact derived from the context, cite the supporting \
citation ID immediately after the claim, e.g. "Employees receive 12 days. [1]"
- Use only the citation IDs that appear in the supplied context. \
Never invent a citation ID that does not exist in the context.
- Do not fabricate page numbers, filenames, or document names.

If the provided context does not contain sufficient information to answer \
the question, respond with:
"The answer cannot be determined from the provided sources."

Do not guess or speculate beyond what the evidence states."""

# ---------------------------------------------------------------------------
# Empty-context fallback block.
# ---------------------------------------------------------------------------
_NO_CONTEXT_BLOCK = "<context>\nNo relevant context was retrieved.\n</context>"


class V2PromptTemplate(BasePromptTemplate):
    """
    Grounded + citation prompt template (V2).

    Structure:
        SYSTEM  → grounding rules + citation requirements + no-answer rule
        USER    → <context>...</context> then <question>...</question>

    Delimiters separate retrieved evidence from system instructions and from
    the user query, reducing the risk of context content being misread as
    an instruction.
    """

    @property
    def version(self) -> PromptVersion:
        return PromptVersion.V2

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT_V2

    def build(self, query: str, context: BuiltContext) -> Prompt:
        """
        Assemble V2 prompt with context delimiters.

        User message structure:
            <context>
            [1]
            source: ...
            ...evidence...
            </context>

            <question>
            user query
            </question>
        """
        citation_ids = self._extract_citation_ids(context)

        if context.context_text.strip():
            context_block = f"<context>\n{context.context_text}\n</context>"
        else:
            context_block = _NO_CONTEXT_BLOCK

        user_content = f"{context_block}\n\n<question>\n{query}\n</question>"

        messages = [
            PromptMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT_V2),
            PromptMessage(role=MessageRole.USER, content=user_content),
        ]

        return Prompt(
            version=self.version,
            system_prompt=_SYSTEM_PROMPT_V2,
            context_text=context.context_text,
            query=query,
            messages=messages,
            citation_ids=citation_ids,
        )
