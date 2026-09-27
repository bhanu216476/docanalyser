"""
Tests for evaluation dataset models and validation rules.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from evals.models import (
    EvaluationCase,
    EvaluationCategory,
    EvaluationDataset,
    RetrievalConfig,
    RetrievalMetrics,
)


def test_valid_evaluation_case_creation() -> None:
    case = EvaluationCase(
        id="eval-001",
        question="What is the default line length?",
        category=EvaluationCategory.SIMPLE_LOOKUP,
        expected_answer="88 characters",
        relevant_document_ids=["doc-001"],
        relevant_chunk_ids=["doc-001:0"],
        expected_citations=["[1]"],
        answerable=True,
    )
    assert case.id == "eval-001"
    assert case.category == EvaluationCategory.SIMPLE_LOOKUP
    assert case.answerable is True


def test_evaluation_case_empty_question_fails() -> None:
    with pytest.raises(ValidationError):
        EvaluationCase(
            id="eval-002",
            question="   ",
            category=EvaluationCategory.SIMPLE_LOOKUP,
            expected_answer="Something",
            relevant_chunk_ids=["c1"],
            answerable=True,
        )


def test_evaluation_case_missing_ground_truth_for_answerable_fails() -> None:
    # Missing chunk/doc IDs
    with pytest.raises(ValidationError):
        EvaluationCase(
            id="eval-003",
            question="Where is this?",
            category=EvaluationCategory.SIMPLE_LOOKUP,
            expected_answer="Valid answer",
            relevant_document_ids=[],
            relevant_chunk_ids=[],
            answerable=True,
        )

    # Empty expected answer
    with pytest.raises(ValidationError):
        EvaluationCase(
            id="eval-004",
            question="Where is this?",
            category=EvaluationCategory.SIMPLE_LOOKUP,
            expected_answer="   ",
            relevant_chunk_ids=["c1"],
            answerable=True,
        )


def test_unanswerable_case_allows_empty_chunks() -> None:
    case = EvaluationCase(
        id="eval-unans",
        question="What is the lunar base policy?",
        category=EvaluationCategory.NO_ANSWER,
        expected_answer="The corpus does not contain this information.",
        relevant_chunk_ids=[],
        answerable=False,
    )
    assert case.answerable is False
    assert len(case.relevant_chunk_ids) == 0


def test_dataset_loading_detects_duplicate_ids(tmp_path: Path) -> None:
    file = tmp_path / "dataset.jsonl"
    lines = [
        json.dumps({
            "id": "eval-001",
            "question": "Question 1?",
            "category": "simple_lookup",
            "expected_answer": "Answer 1",
            "relevant_chunk_ids": ["c1"],
            "answerable": True,
        }),
        json.dumps({
            "id": "eval-001",  # Duplicate ID
            "question": "Question 2?",
            "category": "semantic",
            "expected_answer": "Answer 2",
            "relevant_chunk_ids": ["c2"],
            "answerable": True,
        }),
    ]
    file.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate evaluation case ID 'eval-001'"):
        EvaluationDataset.load_from_jsonl(file)


def test_dataset_loading_detects_invalid_json(tmp_path: Path) -> None:
    file = tmp_path / "dataset_bad.jsonl"
    file.write_text("{ not valid json }\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        EvaluationDataset.load_from_jsonl(file)


def test_dataset_loading_detects_invalid_category(tmp_path: Path) -> None:
    file = tmp_path / "dataset_bad_cat.jsonl"
    bad_line = json.dumps({
        "id": "eval-005",
        "question": "Question?",
        "category": "not_a_valid_category",
        "expected_answer": "Answer",
        "relevant_chunk_ids": ["c1"],
        "answerable": True,
    })
    file.write_text(bad_line, encoding="utf-8")

    with pytest.raises(ValidationError):
        EvaluationDataset.load_from_jsonl(file)
