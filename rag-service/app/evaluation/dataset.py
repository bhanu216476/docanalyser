from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationCase(BaseModel):
    """Deterministic evaluation case for retrieval or end-to-end RAG testing."""

    id: str = Field(..., min_length=1, description="Unique case identifier.")
    question: str = Field(..., min_length=1, description="Question to ask the RAG system.")
    expected_answer: str | None = Field(
        default=None,
        description="Optional canonical answer for end-to-end evaluation.",
    )
    relevant_document_ids: list[str] | None = Field(
        default=None,
        description="Optional document IDs that are relevant to the question.",
    )
    relevant_chunk_ids: list[str] | None = Field(
        default=None,
        description="Optional chunk IDs that are relevant to the question.",
    )
    expected_citations: list[int] | None = Field(
        default=None,
        description="Optional expected citation IDs for the answer.",
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question cannot be empty")
        return stripped


def load_evaluation_dataset(path: str | Path) -> list[EvaluationCase]:
    """Load a JSON or JSONL evaluation dataset into EvaluationCase objects."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")

    if dataset_path.suffix.lower() == ".jsonl":
        return _load_jsonl(dataset_path)
    if dataset_path.suffix.lower() == ".json":
        return _load_json(dataset_path)

    raise ValueError(f"Unsupported evaluation dataset format: {dataset_path.suffix}")


def _load_json(path: Path) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("cases") or payload.get("items")
    if not isinstance(payload, list):
        raise ValueError("JSON evaluation dataset must contain a list of cases or a 'cases' field.")
    return [_normalize_case(item) for item in payload]


def _load_jsonl(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
            raise ValueError(f"Invalid JSONL at line {line_number}: {line}") from exc
        cases.append(_normalize_case(obj))
    if not cases:
        raise ValueError("Evaluation JSONL dataset is empty.")
    return cases


def _normalize_case(payload: Any) -> EvaluationCase:
    if not isinstance(payload, dict):
        raise ValueError(f"Each evaluation case must be an object, got {type(payload).__name__}")
    if "id" not in payload or "question" not in payload:
        raise ValueError("Each evaluation case must include 'id' and 'question'.")
    return EvaluationCase(**payload)
