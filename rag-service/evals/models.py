"""
Evaluation data models and schema definitions.

Defines:
- EvaluationCategory: Category enum covering the required question types.
- RetrievalConfig: Evaluated retrieval configuration options.
- EvaluationCase: Strongly-typed model for single evaluation cases with ground truth.
- EvaluationDataset: Dataset wrapper supporting JSONL loading and schema validation.
- RetrievalMetrics: Per-query retrieval accuracy metrics (Recall@K, MRR, Context Relevance).
- CaseEvaluationResult: Complete per-case evaluation output across all dimensions.
- ConfigurationEvaluationSummary: Dataset-level aggregated summary and category breakdowns.
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationCategory(str, Enum):
    """Categories covering different retrieval and answer-generation scenarios."""

    SIMPLE_LOOKUP = "simple_lookup"
    SEMANTIC = "semantic"
    EXACT_KEYWORD = "exact_keyword"
    MULTI_HOP = "multi_hop"
    AMBIGUOUS = "ambiguous"
    NO_ANSWER = "no_answer"
    CONFLICTING = "conflicting"


class RetrievalConfig(str, Enum):
    """Retrieval configurations evaluated in the baseline framework."""

    DENSE = "dense"
    BM25 = "bm25"
    HYBRID = "hybrid"
    HYBRID_RERANKING = "hybrid_reranking"


class EvaluationCase(BaseModel):
    """
    Strongly-typed model for a single evaluation case.

    Attributes:
        id: Unique identifier (e.g. 'eval-001').
        question: The user query to evaluate.
        category: Question category.
        expected_answer: Ground-truth reference answer.
        relevant_document_ids: List of canonical document IDs containing required evidence.
        relevant_chunk_ids: List of chunk IDs containing required evidence.
        expected_citations: Expected citation references (e.g. chunk IDs or markers).
        answerable: Whether the question is answerable from the indexed corpus.
        required_evidence: Optional list of specific evidence snippets.
        notes: Optional context or annotation explaining ambiguities/conflicts.
    """

    id: str = Field(..., min_length=1, description="Unique case identifier.")
    question: str = Field(..., min_length=1, description="Query text.")
    category: EvaluationCategory = Field(..., description="Evaluation category.")
    expected_answer: str = Field(default="", description="Ground-truth reference answer.")
    relevant_document_ids: list[str] = Field(
        default_factory=list, description="IDs of relevant source documents."
    )
    relevant_chunk_ids: list[str] = Field(
        default_factory=list, description="IDs of relevant chunks."
    )
    expected_citations: list[str] = Field(
        default_factory=list, description="Expected citation identifiers."
    )
    answerable: bool = Field(default=True, description="Whether question is answerable.")
    required_evidence: Optional[list[str]] = Field(
        default=None, description="Key verbatim evidence fragments required."
    )
    notes: Optional[str] = Field(
        default=None, description="Additional context or notes."
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("question")
    @classmethod
    def validate_question_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Evaluation question cannot be empty or whitespace.")
        return v.strip()

    @model_validator(mode="after")
    def validate_answerable_consistency(self) -> EvaluationCase:
        if self.answerable:
            if not self.relevant_chunk_ids and not self.relevant_document_ids:
                raise ValueError(
                    f"Case '{self.id}' is answerable but provides no relevant chunk or document IDs."
                )
            if not self.expected_answer.strip():
                raise ValueError(
                    f"Case '{self.id}' is answerable but provides an empty expected_answer."
                )
        return self


class RetrievalMetrics(BaseModel):
    """Retrieval accuracy metrics for a single query."""

    recall_at_1: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_3: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_5: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    context_relevance_at_5: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)


class CaseEvaluationResult(BaseModel):
    """
    Per-question evaluation outcome across retrieval, answer, citation, and latency.
    """

    evaluation_id: str
    question: str
    category: EvaluationCategory
    configuration: RetrievalConfig
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    answer: str
    ground_truth_answer: str
    answerable: bool = True
    retrieval_metrics: RetrievalMetrics
    answer_correctness: float = Field(default=0.0, ge=0.0, le=1.0)
    faithfulness: float = Field(default=0.0, ge=0.0, le=1.0)
    context_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    correct_abstention: Optional[bool] = None
    latency_breakdown_ms: dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0

    model_config = ConfigDict(frozen=True)


class ConfigurationEvaluationSummary(BaseModel):
    """
    Aggregated evaluation summary for a specific retrieval configuration.
    """

    evaluation_version: str = "rag_eval_v1"
    configuration: str
    dataset_size: int
    metrics: dict[str, float]
    per_category_metrics: dict[str, dict[str, float]]
    latency_summary_ms: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Per-stage and total latency stats (mean, median, p95).",
    )
    failure_cases: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Inspectable list of failing cases (retrieval miss, hallucination, bad citation).",
    )

    model_config = ConfigDict(frozen=True)


class EvaluationDataset(BaseModel):
    """
    Dataset collection with loading and validation utilities.
    """

    cases: list[EvaluationCase] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)

    @classmethod
    def load_from_jsonl(cls, file_path: Union[str, Path]) -> EvaluationDataset:
        """Load and validate an evaluation dataset from a JSONL file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Evaluation dataset file not found: {path}")

        cases: list[EvaluationCase] = []
        seen_ids: set[str] = set()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as err:
                    raise ValueError(
                        f"Invalid JSON at line {line_no} in {path.name}: {err}"
                    ) from err

                case = EvaluationCase.model_validate(data)
                if case.id in seen_ids:
                    raise ValueError(
                        f"Duplicate evaluation case ID '{case.id}' at line {line_no}."
                    )
                seen_ids.add(case.id)
                cases.append(case)

        return cls(cases=cases)

    def save_to_jsonl(self, file_path: Union[str, Path]) -> None:
        """Save dataset to a JSONL file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for case in self.cases:
                f.write(case.model_dump_json() + "\n")

    def __len__(self) -> int:
        return len(self.cases)
