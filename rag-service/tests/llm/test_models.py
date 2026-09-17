import pytest
from pydantic import ValidationError

from app.llm.models import LLMRequest, LLMResponse


def test_valid_request_and_response_are_frozen() -> None:
    request = LLMRequest(prompt="Explain this", max_output_tokens=50, temperature=0.2)
    response = LLMResponse(
        text="An explanation", model="test-model", input_tokens=4,
        output_tokens=3, total_tokens=7,
    )
    assert request.prompt == "Explain this"
    assert response.total_tokens == 7
    with pytest.raises(ValidationError):
        request.prompt = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_empty_prompt_rejected(prompt: str) -> None:
    with pytest.raises(ValidationError):
        LLMRequest(prompt=prompt)


def test_invalid_request_options_rejected() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(prompt="valid", max_output_tokens=0)
    with pytest.raises(ValidationError):
        LLMRequest(prompt="valid", temperature=2.1)