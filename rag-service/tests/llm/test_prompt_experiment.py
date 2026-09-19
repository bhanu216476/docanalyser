"""Tests for Prompt Experiment Framework (runner, cases, report, provider)."""

from __future__ import annotations

import pytest

from app.context.models import BuiltContext, Citation, ContextChunk
from app.llm.dataset import EXPERIMENT_CASES, CASE_C1, CASE_C3
from app.llm.experiment import (
    PromptExperimentCase,
    PromptExperimentRecord,
    PromptExperimentReport,
    PromptExperimentRunner,
)
from app.llm.prompt_builder import PromptBuilder
from app.llm.prompts.models import PromptVersion
from app.llm.providers import FakeLLMProvider, LLMResponse


class TestPromptExperimentCase:
    def test_case_attributes(self) -> None:
        case = CASE_C1
        assert case.case_id == "C1"
        assert len(case.query) > 0
        assert case.context is not None
        assert case.context.is_empty is False
        assert len(case.expected_behavior) > 0

    def test_case_c3_empty_context(self) -> None:
        case = CASE_C3
        assert case.case_id == "C3"
        assert case.context.is_empty is True
        assert len(case.context.selected_chunks) == 0


class TestFakeLLMProvider:
    def test_offline_generation_no_api_keys(self) -> None:
        provider = FakeLLMProvider()
        builder = PromptBuilder()
        prompt = builder.build(query=CASE_C1.query, context=CASE_C1.context, version=PromptVersion.V2)
        response = provider.generate(prompt)

        assert isinstance(response, LLMResponse)
        assert response.version is PromptVersion.V2
        assert response.latency_ms >= 0.0
        assert response.prompt_tokens > 0
        assert "[1]" in response.response_text

    def test_custom_response_override(self) -> None:
        provider = FakeLLMProvider(
            custom_responses={PromptVersion.V1: "Custom V1 output"}
        )
        builder = PromptBuilder()
        prompt = builder.build(query=CASE_C1.query, context=CASE_C1.context, version=PromptVersion.V1)
        response = provider.generate(prompt)
        assert response.response_text == "Custom V1 output"


class TestPromptExperimentRunner:
    def test_run_single_case(self) -> None:
        runner = PromptExperimentRunner()
        record = runner.run_case(CASE_C1, PromptVersion.V2)

        assert isinstance(record, PromptExperimentRecord)
        assert record.case_id == "C1"
        assert record.prompt_version is PromptVersion.V2
        assert len(record.response) > 0
        assert record.latency_ms >= 0.0
        assert record.prompt_tokens > 0
        assert record.grounded is None  # default None for manual eval

    def test_run_single_case_with_string_version(self) -> None:
        runner = PromptExperimentRunner()
        record = runner.run_case(CASE_C1, "v3")
        assert record.prompt_version is PromptVersion.V3

    def test_run_all_cases_and_versions(self) -> None:
        runner = PromptExperimentRunner()
        # Run across all 6 cases and 3 versions = 18 combinations
        report = runner.run_all(cases=EXPERIMENT_CASES)

        assert isinstance(report, PromptExperimentReport)
        assert report.cases_run == 18
        assert len(report.records) == 18
        assert len(report.versions_tested) == 3
        assert len(report.comparison_table) > 0
        assert "| Case |" in report.comparison_table
        assert "C1" in report.comparison_table
        assert "C6" in report.comparison_table

    def test_run_all_custom_subset(self) -> None:
        runner = PromptExperimentRunner()
        report = runner.run_all(
            cases=[CASE_C1, CASE_C3],
            versions=[PromptVersion.V1, PromptVersion.V2],
        )
        assert report.cases_run == 4
        assert len(report.records) == 4
        assert report.versions_tested == [PromptVersion.V1, PromptVersion.V2]
