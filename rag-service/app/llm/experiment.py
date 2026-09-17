"""
Prompt Experiment Framework.

Runs controlled prompt experiments comparing V1, V2, and V3 prompt templates
against a fixed set of experiment cases. The only intentional variable between
runs is the prompt version — query, context, and LLM configuration are held
constant.

Mirrors the pattern established in app/reranking/experiment.py.

Usage:
    runner = PromptExperimentRunner(
        builder=PromptBuilder(),
        provider=FakeLLMProvider(),
    )
    report = runner.run_all(cases=EXPERIMENT_CASES, versions=[V1, V2, V3])
    print(report.comparison_table)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.context.models import BuiltContext, Citation, ContextChunk
from app.llm.prompt_builder import PromptBuilder
from app.llm.prompts.models import PromptVersion
from app.llm.providers import FakeLLMProvider, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Experiment input model
# ---------------------------------------------------------------------------


class PromptExperimentCase(BaseModel):
    """
    A single experiment case representing one query-context pair.

    Attributes:
        case_id: Short identifier (e.g. 'C1', 'C2').
        query: The user question for this case.
        context: Pre-built BuiltContext from the Context Builder.
        expected_behavior: Human-readable description of the correct response
                           behavior. Used as documentation for manual evaluation.
    """

    case_id: str = Field(..., min_length=1, description="Unique case identifier.")
    query: str = Field(..., min_length=1, description="User question string.")
    context: BuiltContext = Field(
        ...,
        description="Pre-assembled BuiltContext to use as evidence.",
    )
    expected_behavior: str = Field(
        default="",
        description="Expected grounding behavior for manual evaluation reference.",
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Per-run result record
# ---------------------------------------------------------------------------


class PromptExperimentRecord(BaseModel):
    """
    Result for one (case × prompt version) run.

    Evaluation fields (grounded, citation_correct, etc.) are nullable because
    automatic evaluation is unreliable. These fields are designed for manual
    annotation after review, or for future automated scoring integration.

    Attributes:
        case_id: Experiment case identifier.
        prompt_version: Prompt version applied.
        response: LLM response text.
        latency_ms: Total latency for this run (prompt build + LLM call).
        prompt_tokens: Token count of the assembled prompt input.
        grounded: Whether the response is grounded in the supplied context.
        citation_correct: Whether cited IDs are all valid (no hallucinated IDs).
        citation_complete: Whether all relevant citations were used.
        answered: Whether the question was answered (vs. "cannot determine").
        hallucination_detected: Whether the response contains invented facts.
    """

    case_id: str = Field(..., description="Experiment case identifier.")
    prompt_version: PromptVersion = Field(..., description="Prompt version used.")
    response: str = Field(..., description="LLM response text.")
    latency_ms: float = Field(..., ge=0.0, description="Total latency in ms.")
    prompt_tokens: int = Field(default=0, ge=0, description="Prompt token count.")

    # Evaluation fields — nullable for manual or deferred assessment.
    grounded: Optional[bool] = Field(
        default=None,
        description="Response is grounded in supplied context (manual eval).",
    )
    citation_correct: Optional[bool] = Field(
        default=None,
        description="All cited IDs exist in the context (no hallucinated IDs).",
    )
    citation_complete: Optional[bool] = Field(
        default=None,
        description="All relevant context sources are cited.",
    )
    answered: Optional[bool] = Field(
        default=None,
        description="The question received a substantive answer.",
    )
    hallucination_detected: Optional[bool] = Field(
        default=None,
        description="Response contains facts not supported by the context.",
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Batch report
# ---------------------------------------------------------------------------


class PromptExperimentReport(BaseModel):
    """
    Summary of a full prompt experiment run.

    Attributes:
        cases_run: Total number of (case × version) combinations executed.
        versions_tested: Prompt versions evaluated.
        records: All individual PromptExperimentRecord results.
        comparison_table: Markdown-formatted comparison table for easy review.
    """

    cases_run: int = Field(..., ge=0, description="Total runs executed.")
    versions_tested: list[PromptVersion] = Field(
        default_factory=list,
        description="Prompt versions evaluated in this experiment.",
    )
    records: list[PromptExperimentRecord] = Field(
        default_factory=list,
        description="All individual experiment run records.",
    )
    comparison_table: str = Field(
        default="",
        description="Markdown comparison table of all results.",
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------


class PromptExperimentRunner:
    """
    Runs controlled prompt experiments across cases and prompt versions.

    Holds query, context, and LLM provider constant across runs.
    The only intentional variable is the prompt version, ensuring
    results isolate prompt design as the independent variable.

    Args:
        builder: PromptBuilder instance with the registered version templates.
        provider: LLMProvider to use for generation (use FakeLLMProvider for tests).
    """

    def __init__(
        self,
        builder: Optional[PromptBuilder] = None,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        self._builder = builder or PromptBuilder()
        self._provider: LLMProvider = provider or FakeLLMProvider()

    def run_all(
        self,
        cases: list[PromptExperimentCase],
        versions: Optional[list[PromptVersion]] = None,
    ) -> PromptExperimentReport:
        """
        Run all cases against all (or specified) prompt versions.

        Each (case × version) pair is an isolated run. No state is shared
        between runs.

        Args:
            cases: List of PromptExperimentCase to evaluate.
            versions: Subset of PromptVersions to test. Defaults to all registered.

        Returns:
            PromptExperimentReport with all records and a comparison table.
        """
        resolved_versions = versions or self._builder.registered_versions()
        records: list[PromptExperimentRecord] = []

        for case in cases:
            for version in resolved_versions:
                record = self._run_single(case, version)
                records.append(record)
                logger.info(
                    "Experiment run: case=%s version=%s latency=%.1fms",
                    case.case_id,
                    version.value,
                    record.latency_ms,
                )

        table = _build_comparison_table(records, resolved_versions)

        return PromptExperimentReport(
            cases_run=len(records),
            versions_tested=resolved_versions,
            records=records,
            comparison_table=table,
        )

    def run_case(
        self,
        case: PromptExperimentCase,
        version: PromptVersion | str,
    ) -> PromptExperimentRecord:
        """
        Run a single case against a single prompt version.

        Args:
            case: The experiment case to evaluate.
            version: PromptVersion or version string.

        Returns:
            A single PromptExperimentRecord.
        """
        resolved = (
            PromptVersion.from_string(version)
            if isinstance(version, str)
            else version
        )
        return self._run_single(case, resolved)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_single(
        self,
        case: PromptExperimentCase,
        version: PromptVersion,
    ) -> PromptExperimentRecord:
        """Execute one (case × version) run and return a record."""
        t_start = time.perf_counter()

        prompt = self._builder.build(
            query=case.query,
            context=case.context,
            version=version,
        )
        response: LLMResponse = self._provider.generate(prompt)

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        return PromptExperimentRecord(
            case_id=case.case_id,
            prompt_version=version,
            response=response.response_text,
            latency_ms=total_latency_ms,
            prompt_tokens=response.prompt_tokens,
            # Evaluation fields left null — to be filled by manual review
            # or an automated scoring pass.
        )


# ---------------------------------------------------------------------------
# Comparison table formatter
# ---------------------------------------------------------------------------


def _build_comparison_table(
    records: list[PromptExperimentRecord],
    versions: list[PromptVersion],
) -> str:
    """
    Build a markdown comparison table from experiment records.

    Columns: Case | Prompt | Answered | Grounded | Citation Correct | Latency
    """
    if not records:
        return "| Case | Prompt | Answered | Grounded | Citation Correct | Latency (ms) |\n|---|---|---|---|---|---|\n| - | - | - | - | - | - |"

    def _fmt(val: Optional[bool]) -> str:
        if val is None:
            return "-"
        return "Yes" if val else "No"

    header = (
        "| Case | Prompt | Answered | Grounded | Citation Correct | Latency (ms) |\n"
        "|------|--------|----------|----------|------------------|--------------|\n"
    )

    # Sort by case_id then version
    sorted_records = sorted(
        records, key=lambda r: (r.case_id, r.prompt_version.value)
    )

    rows = []
    for r in sorted_records:
        rows.append(
            f"| {r.case_id} "
            f"| {r.prompt_version.value.upper()} "
            f"| {_fmt(r.answered)} "
            f"| {_fmt(r.grounded)} "
            f"| {_fmt(r.citation_correct)} "
            f"| {r.latency_ms:.1f} |"
        )

    return header + "\n".join(rows)


if __name__ == "__main__":
    from app.llm.dataset import EXPERIMENT_CASES

    runner = PromptExperimentRunner()
    report = runner.run_all(EXPERIMENT_CASES)
    print("=" * 60)
    print("PROMPT EXPERIMENT REPORT")
    print(f"Total runs: {report.cases_run}")
    print(f"Versions tested: {[v.value for v in report.versions_tested]}")
    print("=" * 60)
    print(report.comparison_table)
