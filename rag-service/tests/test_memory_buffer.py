"""
Tests for Token-Budgeted Conversational Memory in DocAnalyser.
"""

from app.memory.buffer import TokenBudgetedMemoryBuffer, estimate_tokens


def test_token_estimation():
    text = "DocAnalyser provides intelligent hybrid retrieval."
    tokens = estimate_tokens(text)
    assert tokens >= 5


def test_token_budgeted_memory_formatting():
    buffer = TokenBudgetedMemoryBuffer(max_tokens=200)

    history = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! I am Maddy."},
        {"role": "user", "content": "What is hybrid RAG?"},
        {"role": "assistant", "content": "Hybrid RAG fuses vector search with sparse BM25 retrieval for high accuracy."},
        {"role": "user", "content": "What is the second benefit?"},
    ]

    budgeted = buffer.format_history_for_llm(history, max_budget=100)
    assert len(budgeted) >= 2
    # Chronological ordering preserved
    assert budgeted[-1]["role"] == "user"
    assert "second benefit" in budgeted[-1]["content"]


def test_session_state_and_reset():
    buffer = TokenBudgetedMemoryBuffer(max_tokens=500, summary_threshold_turns=3)
    session_id = "test-session-123"

    buffer.add_turn(session_id, "user", "First question about architecture.")
    buffer.add_turn(session_id, "assistant", "First answer describing the components.")
    buffer.add_turn(session_id, "user", "Second question about databases.")
    buffer.add_turn(session_id, "assistant", "Second answer describing PostgreSQL.")

    state = buffer.get_or_create_session(session_id)
    assert len(state.turns) >= 2
    assert state.total_tokens > 0

    buffer.reset_session(session_id)
    new_state = buffer.get_or_create_session(session_id)
    assert len(new_state.turns) == 0
