"""
LLM module.

Provides the Prompt Engineering Layer for the DocAnalyser RAG pipeline:
    Context Builder → BuiltContext → PromptBuilder → Prompt → LLMProvider

Exports:
- PromptBuilder: assembles versioned prompts from query + BuiltContext.
- Prompt, PromptVersion, PromptMessage, MessageRole: prompt data models.
- LLMProvider (Protocol), LLMResponse, FakeLLMProvider: provider abstraction.
- PromptExperimentRunner, PromptExperimentCase, PromptExperimentRecord,
  PromptExperimentReport: experiment framework.
- UnknownPromptVersionError: version registry error.
- EXPERIMENT_CASES: canonical 6-case evaluation dataset.
"""

from app.llm.prompt_builder import PromptBuilder, UnknownPromptVersionError
from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.v1 import V1PromptTemplate
from app.llm.prompts.v2 import V2PromptTemplate
from app.llm.prompts.v3 import V3PromptTemplate
from app.llm.providers import FakeLLMProvider, LLMProvider, LLMResponse
from app.llm.experiment import (
    PromptExperimentCase,
    PromptExperimentRecord,
    PromptExperimentReport,
    PromptExperimentRunner,
)
from app.llm.dataset import EXPERIMENT_CASES

__all__ = [
    # Builder
    "PromptBuilder",
    "UnknownPromptVersionError",
    # Models
    "Prompt",
    "PromptMessage",
    "PromptVersion",
    "MessageRole",
    # Templates
    "BasePromptTemplate",
    "V1PromptTemplate",
    "V2PromptTemplate",
    "V3PromptTemplate",
    # Providers
    "LLMProvider",
    "LLMResponse",
    "FakeLLMProvider",
    # Experiment
    "PromptExperimentCase",
    "PromptExperimentRecord",
    "PromptExperimentReport",
    "PromptExperimentRunner",
    # Dataset
    "EXPERIMENT_CASES",
]
