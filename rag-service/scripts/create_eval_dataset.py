import json
from pathlib import Path


def create_dataset():
    data_dir = Path("evals/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = data_dir / "eval_dataset.jsonl"

    cases = [
        {
            "id": "eval-001",
            "question": "What is DocAnalyser?",
            "category": "simple_lookup",
            "expected_answer": "DocAnalyser is an Enterprise RAG Platform.",
            "relevant_document_ids": ["doc-1"],
            "relevant_chunk_ids": ["chunk-1"],
            "expected_citations": ["chunk-1"],
            "answerable": True,
        },
        {
            "id": "eval-002",
            "question": "How does Hybrid RAG work?",
            "category": "semantic",
            "expected_answer": "Hybrid RAG combines dense and BM25 retrievers.",
            "relevant_document_ids": ["doc-2"],
            "relevant_chunk_ids": ["chunk-2"],
            "expected_citations": ["chunk-2"],
            "answerable": True,
        },
    ]

    with open(dataset_path, "w") as f:
        f.writelines(json.dumps(case) + "\n" for case in cases)

    print(f"Created evaluation dataset at {dataset_path} with {len(cases)} cases.")


if __name__ == "__main__":
    create_dataset()
