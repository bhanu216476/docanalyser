import pytest
from pydantic import ValidationError

from app.context.models import StructuredContext
from app.generation.models import GeneratedAnswer, GenerationRequest


def test_generation_request_is_frozen_and_accepts_context() -> None:
    request = GenerationRequest(query="What is this?", context=StructuredContext())

    assert request.context.item_count == 0
    with pytest.raises(ValidationError):
        request.query = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_generation_request_rejects_empty_query(query: str) -> None:
    with pytest.raises(ValidationError):
        GenerationRequest(query=query, context=StructuredContext())


@pytest.mark.parametrize("answer", ["", "   "])
def test_generated_answer_rejects_empty_answer(answer: str) -> None:
    with pytest.raises(ValidationError):
        GeneratedAnswer(answer=answer, model="test-model")


def test_generated_answer_rejects_negative_token_counts() -> None:
    with pytest.raises(ValidationError):
        GeneratedAnswer(answer="answer", model="test-model", total_tokens=-1)


def test_generated_answer_is_frozen() -> None:
    answer = GeneratedAnswer(answer="answer", model="test-model")

    with pytest.raises(ValidationError):
        answer.answer = "changed"  # type: ignore[misc]