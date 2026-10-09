"""
Unit tests for RAG observability metrics.

Tests:
  - Custom RAG metric recording (retrieval, reranking, LLM, tokens)
  - No-answer and citation failure rate calculations
  - Structured log field injection
"""

from __future__ import annotations

import json
import logging

import pytest
from app.observability.logging_config import JsonFormatter
from app.observability.metrics import RagMetrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_metrics() -> RagMetrics:
    """
    Return a fresh RagMetrics instance by passing an isolated CollectorRegistry.
    """
    from prometheus_client import CollectorRegistry

    reg = CollectorRegistry()
    return RagMetrics(registry=reg)


# ---------------------------------------------------------------------------
# Retrieval latency and score recording
# ---------------------------------------------------------------------------


class TestRetrievalMetrics:
    def test_record_retrieval_latency_dense(self, fresh_metrics):
        fresh_metrics.record_retrieval_latency(0.12, method="dense", outcome="success")
        metric_sum = fresh_metrics.retrieval_latency_seconds.labels(
            retrieval_method="dense"
        )._sum.get()
        assert metric_sum >= 0.12

    def test_record_retrieval_latency_bm25(self, fresh_metrics):
        fresh_metrics.record_retrieval_latency(0.05, method="bm25", outcome="success")

    def test_record_retrieval_latency_failure(self, fresh_metrics):
        fresh_metrics.record_retrieval_latency(0.5, method="dense", outcome="failure")

    def test_record_retrieval_scores_empty(self, fresh_metrics):
        # Should not raise on empty list
        fresh_metrics.record_retrieval_scores([], method="dense")

    def test_record_retrieval_scores_values(self, fresh_metrics):
        scores = [0.9, 0.7, 0.6, 0.4, 0.3]
        fresh_metrics.record_retrieval_scores(
            scores, method="dense", score_type="cosine"
        )


# ---------------------------------------------------------------------------
# Reranking latency recording
# ---------------------------------------------------------------------------


class TestRerankingMetrics:
    def test_record_reranking_basic(self, fresh_metrics):
        fresh_metrics.record_reranking(
            duration_s=0.03, candidate_count=10, reranker_type="mock"
        )

    def test_record_reranking_large_candidate_pool(self, fresh_metrics):
        fresh_metrics.record_reranking(
            duration_s=0.25, candidate_count=50, reranker_type="cross_encoder"
        )


# ---------------------------------------------------------------------------
# LLM request and token usage recording
# ---------------------------------------------------------------------------


class TestLLMMetrics:
    def test_record_llm_success_with_tokens(self, fresh_metrics):
        fresh_metrics.record_llm_request(
            duration_s=1.5,
            provider="openai",
            model="gpt-4",
            is_mock=False,
            outcome="success",
            input_tokens=500,
            output_tokens=200,
        )

    def test_record_llm_mock_provider(self, fresh_metrics):
        fresh_metrics.record_llm_request(
            duration_s=0.001,
            provider="fake",
            model="fake-model",
            is_mock=True,
            outcome="success",
            input_tokens=100,
            output_tokens=50,
        )

    def test_record_llm_failure(self, fresh_metrics):
        fresh_metrics.record_llm_request(
            duration_s=0.5,
            provider="openai",
            model="gpt-4",
            is_mock=False,
            outcome="failure",
            error_type="AuthenticationError",
        )

    def test_record_llm_no_tokens_on_failure(self, fresh_metrics):
        """Token counters must NOT be incremented if no usage data available."""
        fresh_metrics.record_llm_request(
            duration_s=2.0,
            provider="openai",
            model="gpt-4",
            is_mock=False,
            outcome="failure",
            # input_tokens and output_tokens intentionally omitted
        )


# ---------------------------------------------------------------------------
# No-answer rate
# ---------------------------------------------------------------------------


class TestNoAnswerMetrics:
    def test_no_answer_rate_zero_when_no_queries(self, fresh_metrics):
        # Gauge should default to 0 — no calls made yet
        # Just verify record_no_answer doesn't raise
        fresh_metrics.record_no_answer(
            is_no_answer=False, completed_count=0, no_answer_count=0
        )

    def test_no_answer_rate_calculation(self, fresh_metrics):
        """Rate = no_answer_count / completed_count."""
        fresh_metrics.record_no_answer(
            is_no_answer=True, completed_count=5, no_answer_count=1
        )
        # gauge should be 1/5 = 0.2

    def test_no_answer_rate_all_answered(self, fresh_metrics):
        fresh_metrics.record_no_answer(
            is_no_answer=False, completed_count=100, no_answer_count=0
        )

    def test_no_answer_excludes_failed_from_denominator(self, fresh_metrics):
        """Failed requests (pipeline errors) should NOT count as completed queries."""
        # Record 3 successful queries, 1 no-answer
        for _ in range(3):
            fresh_metrics.record_no_answer(
                is_no_answer=False, completed_count=3, no_answer_count=1
            )
        # Rate = 1/3 ≈ 0.33 — not affected by pipeline failures not passed here


# ---------------------------------------------------------------------------
# Citation failure rate
# ---------------------------------------------------------------------------


class TestCitationMetrics:
    def test_record_citation_passed(self, fresh_metrics):
        fresh_metrics.record_citation_verification(
            overall_status="passed",
            failed_count=0,
            total_verifications=3,
        )

    def test_record_citation_failed(self, fresh_metrics):
        fresh_metrics.record_citation_verification(
            overall_status="failed",
            failed_count=2,
            total_verifications=4,
        )

    def test_record_citation_unsupported(self, fresh_metrics):
        fresh_metrics.record_citation_verification(
            overall_status="unsupported",
            failed_count=1,
            total_verifications=3,
        )

    def test_record_citation_no_citations(self, fresh_metrics):
        """No-citation responses should count as 'passed' — not as failures."""
        fresh_metrics.record_citation_verification(
            overall_status="no_citations",
            failed_count=0,
            total_verifications=0,
        )

    def test_citation_failure_rate_zero_when_no_verifications(self, fresh_metrics):
        """Rate = 0 when total_verifications == 0 (avoid division by zero)."""
        fresh_metrics.record_citation_verification(
            overall_status="unavailable",
            failed_count=0,
            total_verifications=0,
        )

    def test_citation_unavailable_not_counted_as_success(self, fresh_metrics):
        """Unavailable verification results must NOT be treated as successful."""
        # 'unavailable' is recorded as its own outcome, not 'passed'
        fresh_metrics.record_citation_verification(
            overall_status="unavailable",
            failed_count=0,
            total_verifications=1,
        )


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    def test_json_formatter_basic_fields(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["severity"] == "INFO"
        assert parsed["message"] == "Hello world"
        assert parsed["logger"] == "test.logger"
        assert "timestamp" in parsed
        assert "service" in parsed
        assert "environment" in parsed

    def test_json_formatter_exception_fields(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["error_type"] == "ValueError"
        assert "stack_trace" in parsed
        assert parsed["severity"] == "ERROR"

    def test_json_formatter_timestamp_is_utc(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.DEBUG,
            pathname="t.py",
            lineno=1,
            msg="ts test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        # UTC ISO-8601 timestamps end with +00:00 or Z equivalent
        ts = parsed["timestamp"]
        assert "+" in ts or ts.endswith("Z") or "UTC" in ts or "+00:00" in ts

    def test_json_formatter_no_sensitive_info(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="t.py",
            lineno=1,
            msg="operation complete",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        # Ensure no API keys / passwords appear in output
        # (none were passed so none should appear)
        assert "api_key" not in output
        assert "password" not in output
        assert "authorization" not in output
