from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRecord(BaseModel):
    """Structured record for a single evaluation question run."""

    id: str = Field(..., description="Evaluation case identifier.")
    question: str = Field(..., description="Question asked to the RAG system.")
    status: str = Field(default="completed", description="completed or failed")
    answer: str | None = Field(default=None, description="Generated answer text.")
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_document_ids: list[str] = Field(default_factory=list)
    citations: list[int] = Field(default_factory=list)
    verification_status: str | None = Field(default=None)
    decision_status: str | None = Field(default=None)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    retrieval_metrics: dict[str, float | None] = Field(default_factory=dict)
    grounding_metrics: dict[str, Any] = Field(default_factory=dict)
    decision_metrics: dict[str, float | int | None] = Field(default_factory=dict)
    error: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


class EvaluationReport(BaseModel):
    """Summary of a full automated evaluation run."""

    dataset_name: str = Field(..., description="Name of the evaluation dataset.")
    total_cases: int = Field(..., ge=0)
    completed_cases: int = Field(..., ge=0)
    failed_cases: int = Field(..., ge=0)
    retrieval_metrics: dict[str, float | None] = Field(default_factory=dict)
    grounding_metrics: dict[str, Any] = Field(default_factory=dict)
    decision_metrics: dict[str, float | int | None] = Field(default_factory=dict)
    latency_metrics: dict[str, float] = Field(default_factory=dict)
    records: list[EvaluationRecord] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)

    def export_json(self, path: str | None = None) -> str:
        import json
        from pathlib import Path

        if path is None:
            file_path = Path(f"{self.dataset_name or 'evaluation_report'}.json")
        else:
            file_path = Path(path)
        payload = self.model_dump(mode="json")
        file_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return str(file_path)
