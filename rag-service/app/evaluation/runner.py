from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from app.evaluation.dataset import EvaluationCase, load_evaluation_dataset
from app.evaluation.metrics import (
    compute_decision_metrics,
    compute_grounding_metrics,
    compute_latency_stats,
    compute_retrieval_metrics,
)
from app.evaluation.models import EvaluationRecord, EvaluationReport
from app.pipeline.models import RAGResponse


class EvaluationRunner:
    """Run a deterministic evaluation dataset against a compatible RAG pipeline."""

    def __init__(
        self,
        dataset: Sequence[EvaluationCase] | str | None,
        pipeline: Any | None = None,
    ) -> None:
        if isinstance(dataset, (str, bytes)):
            cases = load_evaluation_dataset(dataset)
        elif dataset is None:
            cases = []
        else:
            cases = list(dataset)
        self.dataset = cases
        self.pipeline = pipeline

    def run(self) -> EvaluationReport:
        records: list[EvaluationRecord] = []
        latencies: list[float] = []
        retrieval_hits: list[float] = []
        retrieval_recalls: list[float] = []
        retrieval_precision: list[float] = []
        retrieval_mrr: list[float] = []
        unsupported_rates: list[float] = []
        citation_coverages: list[float] = []
        citation_correctness: list[float] = []
        answered_count = 0
        refused_count = 0

        for case in self.dataset:
            record = self.evaluate_case(case)
            records.append(record)
            if record.status == "completed":
                latencies.extend(float(value) for value in record.latency_ms.values())
                retrieval = record.retrieval_metrics
                if retrieval.get("hit_rate_at_k") is not None:
                    retrieval_hits.append(float(retrieval["hit_rate_at_k"]))
                if retrieval.get("recall_at_k") is not None:
                    retrieval_recalls.append(float(retrieval["recall_at_k"]))
                if retrieval.get("precision_at_k") is not None:
                    retrieval_precision.append(float(retrieval["precision_at_k"]))
                if retrieval.get("mrr") is not None:
                    retrieval_mrr.append(float(retrieval["mrr"]))
                grounding = record.grounding_metrics
                if grounding.get("unsupported_claim_rate") is not None:
                    unsupported_rates.append(float(grounding["unsupported_claim_rate"]))
                if grounding.get("citation_coverage") is not None:
                    citation_coverages.append(float(grounding["citation_coverage"]))
                if grounding.get("citation_correctness") is not None:
                    citation_correctness.append(float(grounding["citation_correctness"]))
                if record.decision_metrics.get("answered_count") == 1:
                    answered_count += 1
                if record.decision_metrics.get("refused_count") == 1:
                    refused_count += 1

        retrieval_summary = {
            "hit_rate_at_k": _aggregate(retrieval_hits),
            "recall_at_k": _aggregate(retrieval_recalls),
            "precision_at_k": _aggregate(retrieval_precision),
            "mrr": _aggregate(retrieval_mrr),
        }
        grounding_summary = {
            "unsupported_claim_rate": _aggregate(unsupported_rates),
            "citation_coverage": _aggregate(citation_coverages),
            "citation_correctness": _aggregate(citation_correctness),
        }
        decision_summary = compute_decision_metrics(
            total_questions=len(self.dataset),
            answered_questions=answered_count,
            refused_questions=refused_count,
        )

        report = EvaluationReport(
            dataset_name="evaluation_dataset",
            total_cases=len(self.dataset),
            completed_cases=sum(1 for record in records if record.status == "completed"),
            failed_cases=sum(1 for record in records if record.status == "failed"),
            retrieval_metrics=retrieval_summary,
            grounding_metrics=grounding_summary,
            decision_metrics=decision_summary,
            latency_metrics=compute_latency_stats(latencies),
            records=records,
        )
        return report

    def evaluate_case(self, case: EvaluationCase) -> EvaluationRecord:
        if self.pipeline is None:
            raise ValueError("A pipeline implementation is required to run an evaluation.")
        try:
            response = self.pipeline.query(case.question)
        except Exception as exc:
            return EvaluationRecord(
                id=case.id,
                question=case.question,
                status="failed",
                answer=None,
                retrieval_metrics={},
                grounding_metrics={},
                decision_metrics={},
                latency_ms={},
                error=str(exc),
            )

        retrieved_chunk_ids = _collect_metadata_ids(response, "retrieved_chunk_ids")
        retrieved_document_ids = _collect_metadata_ids(response, "retrieved_document_ids")
        relevant_ids = case.relevant_chunk_ids or case.relevant_document_ids or []
        retrieval_metrics = compute_retrieval_metrics(
            retrieved_ids=retrieved_chunk_ids,
            relevant_ids=related_ground_truth(case),
            k=max(1, len(retrieved_chunk_ids)) if retrieved_chunk_ids else 1,
        )

        verification = response.verification
        grounding_metrics = compute_grounding_metrics(verification)
        decision = response.metadata.get("decision", {}) if response.metadata else {}
        should_answer = bool(decision.get("should_answer", True))
        decision_metrics = {
            "answered_count": 1 if should_answer else 0,
            "refused_count": 1 if not should_answer else 0,
            "refusal_rate": 0.0 if should_answer else 1.0,
        }

        latency_ms = {
            key: float(value)
            for key, value in (response.latency_breakdown_ms or {}).items()
        }
        citation_ids = [int(c.id) for c in response.citations if c.id is not None]
        verification_status = None if verification is None else verification.overall_status.value

        return EvaluationRecord(
            id=case.id,
            question=case.question,
            status="completed",
            answer=response.answer,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_document_ids=retrieved_document_ids,
            citations=citation_ids,
            verification_status=verification_status,
            decision_status="answered" if should_answer else "refused",
            confidence_score=(response.confidence.confidence if response.confidence else None),
            latency_ms=latency_ms,
            retrieval_metrics=retrieval_metrics,
            grounding_metrics=grounding_metrics,
            decision_metrics=decision_metrics,
        )


def _collect_metadata_ids(response: RAGResponse, key: str) -> list[str]:
    metadata = response.metadata or {}
    value = metadata.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _aggregate(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _ground_truth_case_ids(case: EvaluationCase) -> list[str]:
    return list(case.relevant_chunk_ids or case.relevant_document_ids or [])


def related_ground_truth(case: EvaluationCase) -> list[str]:
    exact = case.relevant_chunk_ids or case.relevant_document_ids or []
    return list(exact)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic evaluation dataset against the RAG pipeline.")
    parser.add_argument("--dataset", required=True, help="Path to a JSON or JSONL evaluation dataset.")
    parser.add_argument("--output", default="evaluation_results/evaluation_report.json", help="Output path for the JSON report.")
    args = parser.parse_args()

    from app.pipeline.rag_pipeline import create_rag_pipeline

    dataset = load_evaluation_dataset(args.dataset)
    report = EvaluationRunner(dataset=dataset, pipeline=create_rag_pipeline(in_memory=True)).run()
    report.dataset_name = args.dataset.split("/")[-1].split("\\")[-1].rsplit(".", 1)[0]
    report_path = report.export_json(args.output)
    print(json.dumps({
        "dataset_name": report.dataset_name,
        "total_cases": report.total_cases,
        "completed_cases": report.completed_cases,
        "failed_cases": report.failed_cases,
        "output": report_path,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
