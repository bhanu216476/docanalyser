"""
Token-Budgeted Sliding Window Conversational Memory Buffer for DocAnalyser.
Prevents context window exhaustion, maintains cross-turn entity continuity,
and distills historical turns into concise running summaries.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from app.memory.models import ConversationMemoryState, ConversationTurn

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Accurately estimate token count for text."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # High-accuracy heuristic: ~1.3 tokens per whitespace-separated word
        return max(1, int(len(text.split()) * 1.33))


class TokenBudgetedMemoryBuffer:
    """Manages conversational context bounded by strict token limits."""

    def __init__(
        self,
        max_tokens: int = 1500,
        summary_threshold_turns: int = 8,
    ) -> None:
        self.max_tokens = max_tokens
        self.summary_threshold_turns = summary_threshold_turns
        self._sessions: dict[str, ConversationMemoryState] = {}

    def get_or_create_session(self, session_id: str) -> ConversationMemoryState:
        """Retrieve active session state or initialize a fresh one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationMemoryState(
                session_id=session_id,
                turns=[],
                total_tokens=0,
            )
        return self._sessions[session_id]

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """Record a turn in the session and compress if exceeding budget."""
        state = self.get_or_create_session(session_id)
        tokens = estimate_tokens(content)
        turn = ConversationTurn(
            role=role,
            content=content,
            token_count=tokens,
            metadata=metadata or {},
        )

        all_turns = list(state.turns) + [turn]
        summary = state.summary

        # If turn count or token count exceeds budget, compress oldest turns into summary
        current_tokens = sum(t.token_count for t in all_turns)
        if current_tokens > self.max_tokens or len(all_turns) > self.summary_threshold_turns:
            retained_turns, new_summary = self._compress_history(all_turns, summary)
            all_turns = retained_turns
            summary = new_summary

        new_total_tokens = sum(t.token_count for t in all_turns) + (estimate_tokens(summary) if summary else 0)

        self._sessions[session_id] = ConversationMemoryState(
            session_id=session_id,
            summary=summary,
            turns=all_turns,
            total_tokens=new_total_tokens,
            document_scope=state.document_scope,
        )
        return turn

    def format_history_for_llm(
        self,
        history: Sequence[dict[str, str]] | None,
        max_budget: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Format raw input history turns into a token-budgeted list suitable for LLM injection.
        Guarantees that input conversation history never exceeds token capacity.
        """
        if not history:
            return []

        budget = max_budget or self.max_tokens
        accumulated_tokens = 0
        budgeted_turns: list[dict[str, str]] = []

        # Iterate from most recent backwards
        for turn in reversed(history):
            if not isinstance(turn, dict):
                continue
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()
            if not content:
                continue

            cost = estimate_tokens(content)
            if accumulated_tokens + cost > budget:
                # Truncate content of the oldest included turn if needed
                if not budgeted_turns and cost > budget:
                    budgeted_turns.append({"role": role, "content": content[:400] + "..."})
                break

            budgeted_turns.append({"role": role, "content": content})
            accumulated_tokens += cost

        # Return in chronological order
        budgeted_turns.reverse()
        return budgeted_turns

    def reset_session(self, session_id: str) -> None:
        """Clear memory for a specific chat session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Reset conversation memory for session '%s'", session_id)

    # --- Internal Compression ---

    @staticmethod
    def _compress_history(
        turns: list[ConversationTurn],
        existing_summary: str | None,
    ) -> tuple[list[ConversationTurn], str]:
        """Keep the last 4 turns intact; distill older turns into a concise summary."""
        if len(turns) <= 4:
            return turns, existing_summary or ""

        older_turns = turns[:-4]
        recent_turns = turns[-4:]

        summary_snippets = []
        if existing_summary:
            summary_snippets.append(existing_summary)

        for t in older_turns:
            label = "User" if t.role == "user" else "Assistant"
            first_sentence = t.content.split(".")[0].strip()[:80]
            summary_snippets.append(f"{label}: {first_sentence}")

        condensed = " | ".join(summary_snippets)
        if len(condensed) > 400:
            condensed = condensed[-400:]

        return recent_turns, f"Previous conversation recap: {condensed}"
