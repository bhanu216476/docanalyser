"""Tests for prompt data models (PromptVersion, PromptMessage, Prompt)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.prompts.models import MessageRole, Prompt, PromptMessage, PromptVersion


class TestPromptVersion:
    def test_all_members_have_string_values(self) -> None:
        assert PromptVersion.V1.value == "v1"
        assert PromptVersion.V2.value == "v2"
        assert PromptVersion.V3.value == "v3"

    def test_from_string_lowercase(self) -> None:
        assert PromptVersion.from_string("v1") is PromptVersion.V1
        assert PromptVersion.from_string("v2") is PromptVersion.V2
        assert PromptVersion.from_string("v3") is PromptVersion.V3

    def test_from_string_uppercase(self) -> None:
        assert PromptVersion.from_string("V1") is PromptVersion.V1
        assert PromptVersion.from_string("V3") is PromptVersion.V3

    def test_from_string_with_whitespace(self) -> None:
        assert PromptVersion.from_string("  v2  ") is PromptVersion.V2

    def test_from_string_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown prompt version"):
            PromptVersion.from_string("v99")

    def test_from_string_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptVersion.from_string("")


class TestMessageRole:
    def test_system_value(self) -> None:
        assert MessageRole.SYSTEM.value == "system"

    def test_user_value(self) -> None:
        assert MessageRole.USER.value == "user"


class TestPromptMessage:
    def test_valid_system_message(self) -> None:
        msg = PromptMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant.")
        assert msg.role is MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant."

    def test_frozen(self) -> None:
        msg = PromptMessage(role=MessageRole.USER, content="Hello")
        with pytest.raises(ValidationError):
            msg.content = "modified"


class TestPrompt:
    def _make_prompt(self, version: PromptVersion = PromptVersion.V2) -> Prompt:
        messages = [
            PromptMessage(role=MessageRole.SYSTEM, content="System text"),
            PromptMessage(role=MessageRole.USER, content="<context>Evidence</context>\n<question>Q?</question>"),
        ]
        return Prompt(
            version=version,
            system_prompt="System text",
            context_text="Evidence",
            query="Q?",
            messages=messages,
            citation_ids=["[1]", "[2]"],
        )

    def test_has_context_true(self) -> None:
        p = self._make_prompt()
        assert p.has_context is True

    def test_has_context_false_when_empty(self) -> None:
        messages = [
            PromptMessage(role=MessageRole.SYSTEM, content="sys"),
            PromptMessage(role=MessageRole.USER, content="no context"),
        ]
        p = Prompt(
            version=PromptVersion.V1,
            system_prompt="sys",
            context_text="",
            query="q?",
            messages=messages,
            citation_ids=[],
        )
        assert p.has_context is False

    def test_citation_count(self) -> None:
        p = self._make_prompt()
        assert p.citation_count == 2

    def test_frozen(self) -> None:
        p = self._make_prompt()
        with pytest.raises(ValidationError):
            p.query = "modified"

    def test_built_at_is_set(self) -> None:
        p = self._make_prompt()
        assert p.built_at is not None

    def test_version_v1(self) -> None:
        p = self._make_prompt(PromptVersion.V1)
        assert p.version is PromptVersion.V1
