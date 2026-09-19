"""Structural and behavioral tests for V1, V2, and V3 prompt templates."""

from __future__ import annotations

from app.context.models import BuiltContext, Citation, ContextChunk
from app.llm.prompts.models import MessageRole, PromptVersion
from app.llm.prompts.v1 import V1PromptTemplate
from app.llm.prompts.v2 import V2PromptTemplate
from app.llm.prompts.v3 import V3PromptTemplate


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
        source="leave_policy.pdf",
        file_name="leave_policy.pdf",
    )
    formatted = "[1]\nsource: leave_policy.pdf\n\nThe annual leave entitlement is 25 days."
    chunk = ContextChunk(
        citation_id="[1]",
        chunk_id="chunk-1",
        content="The annual leave entitlement is 25 days.",
        formatted_text=formatted,
        token_count=16,
        final_rank=1,
        citation=citation,
    )
    return BuiltContext(
        context_text=formatted,
        token_count=16,
        token_budget=1000,
        selected_chunks=[chunk],
        citations=[citation],
        dropped_chunks_count=0,
    )


class TestV1PromptTemplate:
    def test_version_property(self) -> None:
        template = V1PromptTemplate()
        assert template.version is PromptVersion.V1

    def test_structure_has_system_and_user(self) -> None:
        template = V1PromptTemplate()
        ctx = _make_context()
        prompt = template.build(query="How much leave?", context=ctx)
        assert len(prompt.messages) == 2
        assert prompt.messages[0].role is MessageRole.SYSTEM
        assert prompt.messages[1].role is MessageRole.USER

    def test_v1_uses_plain_labels_not_xml(self) -> None:
        template = V1PromptTemplate()
        ctx = _make_context()
        prompt = template.build(query="How much leave?", context=ctx)
        user_content = prompt.messages[1].content
        assert "CONTEXT:" in user_content
        assert "QUESTION:" in user_content
        assert "<context>" not in user_content
        assert "<question>" not in user_content

    def test_v1_empty_context(self) -> None:
        template = V1PromptTemplate()
        ctx = _make_context(empty=True)
        prompt = template.build(query="How much leave?", context=ctx)
        assert "No relevant context was retrieved." in prompt.messages[1].content


class TestV2PromptTemplate:
    def test_version_property(self) -> None:
        template = V2PromptTemplate()
        assert template.version is PromptVersion.V2

    def test_v2_uses_xml_delimiters(self) -> None:
        template = V2PromptTemplate()
        ctx = _make_context()
        prompt = template.build(query="How much leave?", context=ctx)
        user_content = prompt.messages[1].content
        assert "<context>" in user_content
        assert "</context>" in user_content
        assert "<question>" in user_content
        assert "</question>" in user_content

    def test_v2_system_prompt_has_citation_rules(self) -> None:
        template = V2PromptTemplate()
        sys = template.system_prompt
        assert "Citation rules:" in sys
        assert "citation ID" in sys
        assert "The answer cannot be determined" in sys

    def test_v2_empty_context_delimiter(self) -> None:
        template = V2PromptTemplate()
        ctx = _make_context(empty=True)
        prompt = template.build(query="How much leave?", context=ctx)
        user_content = prompt.messages[1].content
        assert "<context>\nNo relevant context was retrieved.\n</context>" in user_content


class TestV3PromptTemplate:
    def test_version_property(self) -> None:
        template = V3PromptTemplate()
        assert template.version is PromptVersion.V3

    def test_v3_has_11_numbered_rules(self) -> None:
        template = V3PromptTemplate()
        sys = template.system_prompt
        for i in range(1, 12):
            assert f"{i}." in sys, f"Rule {i}. missing from V3 system prompt"

    def test_v3_includes_conflict_handling(self) -> None:
        template = V3PromptTemplate()
        sys = template.system_prompt
        assert "CONFLICT HANDLING" in sys
        assert "disagree" in sys

    def test_v3_includes_prompt_injection_security(self) -> None:
        template = V3PromptTemplate()
        sys = template.system_prompt
        assert "SECURITY" in sys
        assert "ignore previous instructions" in sys

    def test_v3_uses_xml_delimiters(self) -> None:
        template = V3PromptTemplate()
        ctx = _make_context()
        prompt = template.build(query="How much leave?", context=ctx)
        user_content = prompt.messages[1].content
        assert "<context>" in user_content
        assert "</context>" in user_content
        assert "<question>" in user_content
        assert "</question>" in user_content


class TestPromptTemplateInvariants:
    def test_all_templates_preserve_query(self) -> None:
        query = "What is the capital of France?"
        ctx = _make_context()
        for cls in (V1PromptTemplate, V2PromptTemplate, V3PromptTemplate):
            template = cls()
            prompt = template.build(query=query, context=ctx)
            assert prompt.query == query
            assert query in prompt.messages[1].content

    def test_all_templates_preserve_citation_ids(self) -> None:
        ctx = _make_context()
        for cls in (V1PromptTemplate, V2PromptTemplate, V3PromptTemplate):
            template = cls()
            prompt = template.build(query="Q", context=ctx)
            assert prompt.citation_ids == ["[1]"]

    def test_all_templates_preserve_context_text(self) -> None:
        ctx = _make_context()
        for cls in (V1PromptTemplate, V2PromptTemplate, V3PromptTemplate):
            template = cls()
            prompt = template.build(query="Q", context=ctx)
            assert prompt.context_text == ctx.context_text
            assert ctx.context_text in prompt.messages[1].content
