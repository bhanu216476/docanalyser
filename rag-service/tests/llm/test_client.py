import logging

import pytest

from app.llm.client import LLMClient, create_llm_client
from app.llm.exceptions import (
    LLMProviderError,
    LLMRetryExhaustedError,
    LLMTokenLimitError,
    LLMValidationError,
)
from app.llm.models import LLMResponse
from app.llm.providers import FakeLLMProvider, LLMProvider


class CountingCounter:
    def __init__(self, count: int) -> None:
        self.count_value = count
        self.calls: list[str] = []

    def count(self, text: str) -> int:
        self.calls.append(text)
        return self.count_value


def make_client(provider: LLMProvider, counter: CountingCounter, **kwargs: object) -> LLMClient:
    return LLMClient(
        provider=provider,
        model="test-model",
        max_input_tokens=10,
        max_output_tokens=20,
        temperature=0.2,
        timeout=1.0,
        max_retries=2,
        retry_base_delay=1.0,
        token_counter=counter,
        sleep_fn=kwargs.pop("sleep_fn", lambda _: None),
        **kwargs,
    )


def test_token_counter_and_overrides_are_used() -> None:
    provider = FakeLLMProvider()
    counter = CountingCounter(3)
    client = make_client(provider, counter)
    response = client.generate("prompt", max_output_tokens=7, temperature=0.8)
    assert response.text == "FAKE_RESPONSE[prompt]"
    assert counter.calls == ["prompt"]


def test_output_token_override_cannot_exceed_configured_ceiling() -> None:
    provider = FakeLLMProvider()
    client = make_client(provider, CountingCounter(3))

    with pytest.raises(LLMValidationError):
        client.generate("prompt", max_output_tokens=21)

    assert provider.call_count == 0


def test_over_limit_prompt_does_not_call_provider() -> None:
    provider = FakeLLMProvider()
    client = make_client(provider, CountingCounter(11))
    with pytest.raises(LLMTokenLimitError):
        client.generate("sensitive context")
    assert provider.call_count == 0


def test_validation_is_not_retried() -> None:
    provider = FakeLLMProvider()
    client = make_client(provider, CountingCounter(1))
    with pytest.raises(LLMValidationError):
        client.generate(" ")
    assert provider.call_count == 0


def test_transient_failure_retries_and_succeeds() -> None:
    provider = FakeLLMProvider(fail_on_calls={1})
    sleeps: list[float] = []
    client = make_client(provider, CountingCounter(1), sleep_fn=sleeps.append)
    assert client.generate("prompt").text == "FAKE_RESPONSE[prompt]"
    assert provider.call_count == 2
    assert 1.0 <= sleeps[0] <= 1.5


def test_retries_exhausted_and_permanent_error_not_retried() -> None:
    exhausted_provider = FakeLLMProvider(fail_on_calls={1, 2, 3})
    exhausted = make_client(exhausted_provider, CountingCounter(1), sleep_fn=lambda _: None)
    with pytest.raises(LLMRetryExhaustedError) as error:
        exhausted.generate("prompt")
    assert error.value.attempts == 3

    permanent_provider = FakeLLMProvider(permanent_fail_on_calls={1})
    permanent = make_client(permanent_provider, CountingCounter(1), sleep_fn=lambda _: None)
    with pytest.raises(LLMProviderError):
        permanent.generate("prompt")
    assert permanent_provider.call_count == 1


def test_retry_logs_never_include_prompt(caplog: pytest.LogCaptureFixture) -> None:
    prompt = "TOP SECRET DOCUMENT CONTENT"
    provider = FakeLLMProvider(fail_on_calls={1})
    client = make_client(provider, CountingCounter(1), sleep_fn=lambda _: None)
    with caplog.at_level(logging.WARNING):
        client.generate(prompt)
    assert prompt not in caplog.text


def test_factory_uses_fake_provider_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "openai_api_key", "")
    client = create_llm_client(sleep_fn=lambda _: None)
    assert isinstance(client._provider, FakeLLMProvider)
    assert client.generate("hello").text == "FAKE_RESPONSE[hello]"