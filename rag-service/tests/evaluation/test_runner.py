from __future__ import annotations

from app.context.models import Citation
from app.decision.models import DecisionResult
from app.evaluation.dataset import EvaluationCase
from app.evaluation.runner import EvaluationRunner
from app.pipeline.models import RAGResponse
from app.verification.models import ClaimVerificationResult, VerificationResult, VerificationStatus


class FakeEvaluationPipeline:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def query(self, question: str) -> RAGResponse:
        self.calls.append(question)
        citation = Citation(
            id=1,
            citation_id="[1]",
            document="doc-1",
            chunk_id="chunk-1",
            document_id="doc-1",
            file_name="doc-1.txt",
            source="doc-1.txt",
            file_type="txt",
        )
        return RAGResponse(
            query=question,
            answer="This answer is supported by evidence.",
            citations=[citation],
            prompt_version="v1",
            latency_breakdown_ms={
                "retrieval_ms": 30.0,
                "fusion_ms": 10.0,
                "reranking_ms": 15.0,
                "context_building_ms": 20.0,
                "decision_layer_ms": 5.0,
                "prompt_assembly_ms": 12.0,
                "llm_generation_ms": 40.0,
                "total_ms": 132.0,
            },
            metadata={
                "retrieved_chunk_ids": ["chunk-1", "chunk-2"],
                "retrieved_document_ids": ["doc-1"],
                "decision": {"should_answer": True},
            },
            verification=VerificationResult(
                overall_status=VerificationStatus.SUPPORTED,
                claims=[
                    ClaimVerificationResult(
                        claim_id=1,
                        claim="This answer is supported by evidence.",
                        citation_ids=[1],
                        status=VerificationStatus.SUPPORTED,
                    )
                ],
                total_claims=1,
                supported_count=1,
            ),
            confidence=None,
        )


class FailingPipeline:
    def query(self, question: str) -> RAGResponse:
        raise RuntimeError("fail case")


def test_runner_records_successful_cases() -> None:
    pipeline = FakeEvaluationPipeline()
    runner = EvaluationRunner(
        dataset=[EvaluationCase(id="q1", question="What is the answer?", relevant_chunk_ids=["chunk-1"])],
        pipeline=pipeline,
    )

    report = runner.run()

    assert report.total_cases == 1
    assert report.completed_cases == 1
    assert report.failed_cases == 0
    assert len(report.records) == 1
    assert report.records[0].retrieval_metrics["hit_rate_at_k"] == 1.0


def test_runner_does_not_crash_on_failed_case() -> None:
    runner = EvaluationRunner(
        dataset=[
            EvaluationCase(id="q1", question="Good question", relevant_chunk_ids=["chunk-1"]),
            EvaluationCase(id="q2", question="Bad question", relevant_chunk_ids=["chunk-2"]),
        ],
        pipeline=FailingPipeline(),
    )

    report = runner.run()

    assert report.total_cases == 2
    assert report.completed_cases == 0
    assert report.failed_cases == 2
    assert len(report.records) == 2
    assert report.records[0].status == "failed"


def test_deterministic_run_produces_same_metrics() -> None:
    cases = [
        EvaluationCase(id="q1", question="What is the answer?", relevant_chunk_ids=["chunk-1"]),
        EvaluationCase(id="q2", question="When does it happen?", relevant_chunk_ids=["chunk-2"]),
    ]

    report1 = EvaluationRunner(dataset=cases, pipeline=FakeEvaluationPipeline()).run()
    report2 = EvaluationRunner(dataset=cases, pipeline=FakeEvaluationPipeline()).run()

    assert report1.retrieval_metrics["hit_rate_at_k"] == report2.retrieval_metrics["hit_rate_at_k"]
    assert report1.grounding_metrics["unsupported_claim_rate"] == report2.grounding_metrics["unsupported_claim_rate"]
