from app.llm.exceptions import (
    LLMError,
    LLMProviderError,
    LLMRetryExhaustedError,
    LLMTokenLimitError,
    LLMValidationError,
)


def test_exception_hierarchy_and_attributes() -> None:
    cause = LLMProviderError("temporary", is_transient=True)
    token_error = LLMTokenLimitError(12, 10)
    retry_error = LLMRetryExhaustedError(4, cause)

    assert issubclass(LLMValidationError, LLMError)
    assert issubclass(LLMTokenLimitError, LLMError)
    assert issubclass(LLMProviderError, LLMError)
    assert issubclass(LLMRetryExhaustedError, LLMError)
    assert cause.is_transient is True
    assert (token_error.token_count, token_error.max_tokens) == (12, 10)
    assert retry_error.attempts == 4
    assert retry_error.cause is cause
    assert "sensitive prompt" not in str(retry_error)