"""LLM generation client, provider abstractions, and prompt engineering."""

from app.llm.client import LLMClient, create_llm_client
from app.llm.dataset import EXPERIMENT_CASES
from app.llm.exceptions import (
    LLMError,
    LLMProviderError,
    LLMRetryExhaustedError,
    LLMTokenLimitError,
    LLMValidationError,
)
from app.llm.experiment import (
    PromptExperimentCase,
    PromptExperimentRecord,
    PromptExperimentReport,
    PromptExperimentRunner,
)
from app.llm.models import LLMRequest, LLMResponse
from app.llm.prompt_builder import PromptBuilder, UnknownPromptVersionError
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion
from app.llm.prompts.v1 import V1PromptTemplate
from app.llm.prompts.v2 import V2PromptTemplate
from app.llm.prompts.v3 import V3PromptTemplate
from app.llm.providers import FakeLLMProvider, LLMProvider, OpenAILLMProvider

__all__ = [
    "EXPERIMENT_CASES",
    "BasePromptTemplate",
    "FakeLLMProvider",
    "LLMClient",
    "LLMError",
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "LLMRetryExhaustedError",
    "LLMTokenLimitError",
    "LLMValidationError",
    "MessageRole",
    "OpenAILLMProvider",
    "Prompt",
    "PromptBuilder",
    "PromptExperimentCase",
    "PromptExperimentRecord",
    "PromptExperimentReport",
    "PromptExperimentRunner",
    "PromptMessage",
    "PromptVersion",
    "UnknownPromptVersionError",
    "V1PromptTemplate",
    "V2PromptTemplate",
    "V3PromptTemplate",
    "create_llm_client",
]
