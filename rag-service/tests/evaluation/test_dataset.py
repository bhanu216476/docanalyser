import json
from pathlib import Path

import pytest

from app.evaluation.dataset import EvaluationCase, load_evaluation_dataset


def test_loads_single_case_json(tmp_path: Path) -> None:
    payload = [{
        "id": "q001",
        "question": "What are the working hours?",
        "expected_answer": "9 AM to 5 PM",
        "relevant_document_ids": ["doc-1"],
        "relevant_chunk_ids": ["chunk-7"],
        "expected_citations": [1],
    }]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    cases = load_evaluation_dataset(path)

    assert len(cases) == 1
    assert cases[0].id == "q001"
    assert cases[0].question == "What are the working hours?"
    assert cases[0].relevant_document_ids == ["doc-1"]


def test_invalid_dataset_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"wrong": "shape"}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_evaluation_dataset(path)


def test_single_case_model_accepts_optional_fields() -> None:
    case = EvaluationCase(id="q002", question="Does the answer exist?")

    assert case.expected_answer is None
    assert case.relevant_document_ids is None
    assert case.relevant_chunk_ids is None
    assert case.expected_citations is None
