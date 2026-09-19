"""
Prompts sub-package.

Exports all prompt version templates and shared models.
"""

from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion
from app.llm.prompts.base import BasePromptTemplate
from app.llm.prompts.v1 import V1PromptTemplate
from app.llm.prompts.v2 import V2PromptTemplate
from app.llm.prompts.v3 import V3PromptTemplate

__all__ = [
    # Models
    "Prompt",
    "PromptMessage",
    "PromptVersion",
    "MessageRole",
    # Base
    "BasePromptTemplate",
    # Templates
    "V1PromptTemplate",
    "V2PromptTemplate",
    "V3PromptTemplate",
]
