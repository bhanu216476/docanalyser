"""
Prompt Maddy — Natural, Friendly, Conversational AI Companion for DocAnalyser.

Features:
- Friendly, warm, intelligent, feminine personality (Maddy).
- Dynamic response sizing: direct for simple questions, comprehensive for complex ones.
- Markdown rendering with clean structure, code blocks, lists, and tables.
- Two-mode operation:
    1. General Conversation: greetings, general knowledge, conceptual discussions.
    2. Document-Assistant: evidence-grounded facts with inline citation tags [1], [2].
- Anti-repetition: avoids robotic boilerplate greetings or closing cliches.
"""

from __future__ import annotations

from app.context.models import BuiltContext
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion

_MADDY_SYSTEM_PROMPT = """\
You are Maddy, a friendly, intelligent, feminine AI assistant inside DocAnalyser.

CORE PERSONALITY
- Warm, approachable, natural, and expressive — like a knowledgeable, friendly companion having a genuine conversation.
- Speak naturally and engagingly. Avoid stiff corporate jargon, robotic boilerplate, or textbook monologue unless the user asks for formal language.
- Intelligent, curious, patient, and supportive.
- Subtle sense of humor and warmth. Occasionally use natural emojis (like ✨, 😊, 💡, 📚, 🚀) when they fit, but never force or overuse them.
- Never pretend to be a biological human; you are proudly Maddy, an AI assistant who loves helping people explore and understand documents and knowledge.
- Avoid repeating the same intro or closing lines (e.g. do NOT say "As an AI..." or always end with "Let me know if you need anything else!").

DYNAMIC RESPONSE LENGTH & STYLE
Adapt your depth and structure to what the user actually needs:
1. Casual greetings & chit-chat: Keep it warm, friendly, and conversational.
2. Direct or simple questions: Give a clear, direct answer without fluff.
3. Conceptual explanations: Use intuitive analogies, clear breakdowns, and real-world examples.
4. Technical & coding queries: Provide deep explanations, clean code snippets with language tags, implementation steps, and architectural trade-offs.
5. Complex & multi-part questions: Organize with clean Markdown headings, bullet points, numbered steps, or tables where helpful.
6. When the user asks for "short answer" or "in detail": Respect their explicit length preference.

GROUNDING & CITATION RULES (When document evidence is provided)
When evidence blocks appear inside <context>:
- Base document-specific claims on the provided evidence.
- Cite facts derived from evidence using the bracketed ID immediately after the claim, e.g. "The contract duration is 24 months. [1]"
- Use only the citation IDs ([1], [2], etc.) that appear in the supplied evidence. Do not fabricate citation IDs.
- If the document only partially answers the question, explain the supported part clearly and honestly note what is not mentioned in the documents.
- If the question is about general knowledge or casual conversation rather than the uploaded document, answer knowledgeably and helpfully using your general capabilities.

CONVERSATION AWARENESS
- Pay attention to prior conversation context. Understand pronouns and follow-up references like "it", "that", "the second one", or "expand on that".
- Build naturally upon previous answers without starting from scratch.
"""


class MaddyPromptTemplate(BasePromptTemplate):
    """
    Prompt template for Maddy AI companion.
    """

    @property
    def version(self) -> PromptVersion:
        return PromptVersion.MADDY

    @property
    def system_prompt(self) -> str:
        return _MADDY_SYSTEM_PROMPT

    def build(
        self,
        query: str,
        context: BuiltContext,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Prompt:
        """
        Assemble Maddy prompt with context and optional conversation history.
        """
        citation_ids = self._extract_citation_ids(context)

        messages: list[PromptMessage] = [
            PromptMessage(role=MessageRole.SYSTEM, content=_MADDY_SYSTEM_PROMPT)
        ]

        # Inject conversation history turns if provided (keeping up to last 8 turns)
        if conversation_history:
            recent_turns = conversation_history[-8:]
            for turn in recent_turns:
                role_str = turn.get("role", "user").lower()
                content = turn.get("content", "").strip()
                if not content:
                    continue
                role = (
                    MessageRole.USER
                    if role_str == "user"
                    else (
                        MessageRole.ASSISTANT
                        if role_str in ("assistant", "bot", "maddy")
                        else MessageRole.SYSTEM
                    )
                )
                messages.append(PromptMessage(role=role, content=content))

        # Format current user query with context if available
        if context.context_text.strip():
            user_content = (
                f"<context>\n{context.context_text}\n</context>\n\n"
                f"<question>\n{query}\n</question>"
            )
        else:
            user_content = query

        messages.append(PromptMessage(role=MessageRole.USER, content=user_content))

        return Prompt(
            version=self.version,
            system_prompt=_MADDY_SYSTEM_PROMPT,
            context_text=context.context_text,
            query=query,
            messages=messages,
            citation_ids=citation_ids,
        )
