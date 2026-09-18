from app.context.models import ContextItem, StructuredContext
from app.generation.prompt import PromptBuilder


def test_prompt_contains_query_and_exact_formatted_context() -> None:
    formatted_text = "[1] chunk-1\nEvidence with exact spacing."
    context = StructuredContext(formatted_text=formatted_text)

    prompt = PromptBuilder().build("What happened?", context)

    assert "What happened?" in prompt
    assert formatted_text in prompt
    assert prompt.index(formatted_text) > prompt.index("CONTEXT")


def test_prompt_contains_citation_instructions() -> None:
    prompt = PromptBuilder().build("Question", StructuredContext())

    assert "only the supplied evidence" in prompt
    assert "Do not invent facts" in prompt
    assert "existing [n] citation markers" in prompt
    assert "provided evidence is insufficient" in prompt
    assert "Do not create or modify citation numbers" in prompt


def test_prompt_handles_empty_context() -> None:
    prompt = PromptBuilder().build("Question", StructuredContext())

    assert "No evidence was retrieved" in prompt
    assert "Do not invent an answer" in prompt


def test_prompt_is_deterministic() -> None:
    item = ContextItem(position=1, chunk_id="chunk-1", content="Evidence", citation="[1]")
    context = StructuredContext(items=[item], formatted_text="[1] Evidence")

    assert PromptBuilder().build("Question", context) == PromptBuilder().build(
        "Question", context
    )