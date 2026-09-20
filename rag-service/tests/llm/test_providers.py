from types import SimpleNamespace

import pytest

from app.llm.exceptions import LLMProviderError
from app.llm.providers import FakeLLMProvider, OpenAILLMProvider


def test_fake_provider_is_deterministic() -> None:
    provider = FakeLLMProvider()
    first = provider.generate("hello", model="fake", temperature=0.2, max_output_tokens=5)
    second = provider.generate("hello", model="fake", temperature=0.2, max_output_tokens=5)
    assert first == second
    assert provider.call_count == 2


def test_fake_provider_can_simulate_failures() -> None:
    provider = FakeLLMProvider(fail_on_calls={1}, permanent_fail_on_calls={2})
    with pytest.raises(LLMProviderError) as transient:
        provider.generate("hello", model="fake", temperature=0.2, max_output_tokens=5)
    with pytest.raises(LLMProviderError) as permanent:
        provider.generate("hello", model="fake", temperature=0.2, max_output_tokens=5)
    assert transient.value.is_transient is True
    assert permanent.value.is_transient is False


def test_openai_response_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    response = SimpleNamespace(
        output_text="normalized answer",
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=5, output_tokens=3, total_tokens=8),
    )

    class Responses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            assert kwargs["input"] == "prompt"
            return response

    class Client:
        def __init__(self, **kwargs: object) -> None:
            self.responses = Responses()

    fake_openai = SimpleNamespace(
        OpenAI=Client,
        AuthenticationError=AuthenticationError,
        PermissionDeniedError=PermissionDeniedError,
        BadRequestError=BadRequestError,
        NotFoundError=NotFoundError,
        RateLimitError=RateLimitError,
        APITimeoutError=APITimeoutError,
        APIConnectionError=APIConnectionError,
        APIStatusError=APIStatusError,
    )
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)
    result = OpenAILLMProvider("secret", timeout=2).generate(
        "prompt", model="gpt-test", temperature=0.2, max_output_tokens=5
    )
    assert result.text == "normalized answer"
    assert result.total_tokens == 8


@pytest.mark.parametrize(
    ("error_type", "transient"),
    [("AuthenticationError", False), ("RateLimitError", True), ("APITimeoutError", True)],
)
def test_openai_errors_are_classified(
    monkeypatch: pytest.MonkeyPatch, error_type: str, transient: bool
) -> None:
    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        status_code = 500

    classes = {
        "AuthenticationError": AuthenticationError,
        "PermissionDeniedError": PermissionDeniedError,
        "BadRequestError": BadRequestError,
        "NotFoundError": NotFoundError,
        "RateLimitError": RateLimitError,
        "APITimeoutError": APITimeoutError,
        "APIConnectionError": APIConnectionError,
        "APIStatusError": APIStatusError,
    }

    class Responses:
        def create(self, **kwargs: object) -> None:
            raise getattr(__import__("sys").modules["openai"], error_type)()

    class Client:
        def __init__(self, **kwargs: object) -> None:
            self.responses = Responses()

    fake_openai = SimpleNamespace(OpenAI=Client, **classes)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)
    provider = OpenAILLMProvider("secret")
    with pytest.raises(LLMProviderError) as error:
        provider.generate("prompt", model="gpt-test", temperature=0.2, max_output_tokens=5)
    assert error.value.is_transient is transient