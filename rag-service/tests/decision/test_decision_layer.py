"""Unit tests for the evidence decision layer."""

from __future__ import annotations

from app.context.models import BuiltContext, Citation, ContextChunk
from app.decision.layer import DecisionLayer


def make_context(content: str, *, selected: bool = True) -> BuiltContext:
    citation = Citation(citation_id="[1]", chunk_id="chunk-1")
    chunks = []
    if selected:
        chunks.append(
            ContextChunk(
                citation_id="[1]",
                chunk_id="chunk-1",
                content=content,
                formatted_text=f"[1]\n\n{content}",
                token_count=len(content.split()),
                final_rank=1,
                citation=citation,
            )
        )
    return BuiltContext(
        context_text=f"[1]\n\n{content}" if selected else "",
        selected_chunks=chunks,
        citations=[citation] if selected else [],
        token_count=len(content.split()) if selected else 0,
        token_budget=2000,
    )


def test_empty_evidence_is_rejected() -> None:
    result = DecisionLayer().evaluate("annual leave", make_context("" , selected=False))

    assert result.should_answer is False
    assert result.reason == "no_selected_chunks"


def test_no_selected_chunks_is_rejected() -> None:
    result = DecisionLayer().evaluate("annual leave", make_context("annual leave", selected=False))

    assert result.should_answer is False
    assert result.reason == "no_selected_chunks"


def test_weak_irrelevant_evidence_is_rejected() -> None:
    result = DecisionLayer().evaluate(
        "annual leave", make_context("The office parking lot is on the north side.")
    )

    assert result.should_answer is False
    assert result.reason == "irrelevant_evidence"


def test_sufficient_evidence_is_accepted() -> None:
    result = DecisionLayer().evaluate(
        "How many annual leave days?",
        make_context("Employees receive 15 days of annual leave."),
    )

    assert result.should_answer is True
    assert result.reason == "sufficient_evidence"
    assert result.confidence > 0


def test_decision_is_deterministic() -> None:
    layer = DecisionLayer()
    context = make_context("Employees receive 15 days of annual leave.")

    first = layer.evaluate("How many annual leave days?", context)
    second = layer.evaluate("How many annual leave days?", context)

    assert first == second
