"""Tests for PromptBuilder and version registry."""

from __future__ import annotations

import pytest

from app.context.models import BuiltContext, Citation, ContextChunk
from app.llm.prompt_builder import PromptBuilder, UnknownPromptVersionError
from app.llm.prompts.models import MessageRole, PromptVersion


def _make_context(empty: bool = False) -> BuiltContext:
    if empty:
        return BuiltContext(
            context_text="",
            token_count=0,
            token_budget=1000,
            selected_chunks=[],
            citations=[],
            dropped_chunks_count=0,
        )

    citation = Citation(
        citation_id="[1]",
        chunk_id="chunk-1",
        source="fastapi_doc.md",
        file_name="fastapi_doc.md",
    )
    formatted = "[1]\nsource: fastapi_doc.md\n\nFastAPI is a modern web framework for Python."
    chunk = ContextChunk(
        citation_id="[1]",
        chunk_id="chunk-1",
        content="FastAPI is a modern web framework for Python.",
        formatted_text=formatted,
        token_count=15,
        final_rank=1,
        citation=citation,
    )
    return BuiltContext(
        context_text=formatted,
        token_count=15,
        token_budget=1000,
        selected_chunks=[chunk],
        citations=[citation],
        dropped_chunks_count=0,
    )


class TestPromptBuilder:
    def test_default_version_is_v2(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx)
        assert prompt.version is PromptVersion.V2
        assert len(prompt.messages) == 2
        assert prompt.messages[0].role is MessageRole.SYSTEM
        assert prompt.messages[1].role is MessageRole.USER

    def test_build_v1_enum(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx, version=PromptVersion.V1)
        assert prompt.version is PromptVersion.V1
        assert prompt.citation_ids == ["[1]"]

    def test_build_v1_string(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx, version="v1")
        assert prompt.version is PromptVersion.V1

    def test_build_v2_string_case_insensitive(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx, version="  V2  ")
        assert prompt.version is PromptVersion.V2

    def test_build_v3(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx, version=PromptVersion.V3)
        assert prompt.version is PromptVersion.V3

    def test_unknown_version_raises(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        with pytest.raises(UnknownPromptVersionError, match="Unknown prompt version"):
            builder.build(query="What is FastAPI?", context=ctx, version="v99")

    def test_context_text_preserved_verbatim(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        prompt = builder.build(query="What is FastAPI?", context=ctx, version=PromptVersion.V2)
        assert ctx.context_text in prompt.context_text
        assert ctx.context_text in prompt.messages[1].content

    def test_empty_context_handling(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context(empty=True)
        prompt = builder.build(query="What is FastAPI?", context=ctx, version=PromptVersion.V2)
        assert prompt.has_context is False
        assert prompt.citation_ids == []
        assert len(prompt.messages) == 2

    def test_registered_versions_list(self) -> None:
        builder = PromptBuilder()
        versions = builder.registered_versions()
        assert PromptVersion.V1 in versions
        assert PromptVersion.V2 in versions
        assert PromptVersion.V3 in versions

    def test_query_in_user_message(self) -> None:
        builder = PromptBuilder()
        ctx = _make_context()
        q = "How does dependency injection work?"
        prompt = builder.build(query=q, context=ctx)
        assert q in prompt.messages[1].content
        assert prompt.query == q
