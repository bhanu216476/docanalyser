from app.retrieval.benchmark import (
    format_comparison,
    run_synthetic_benchmark,
)


def test_synthetic_benchmark_returns_perfect_top1_results():
    comparison = run_synthetic_benchmark(top_k=1)

    assert len(comparison.queries) == 3
    assert comparison.dense.hit_rate_at_k == 1.0
    assert comparison.dense.recall_at_k == 1.0
    assert comparison.dense.mrr_at_k == 1.0
    assert comparison.bm25.hit_rate_at_k == 1.0
    assert comparison.bm25.recall_at_k == 1.0
    assert comparison.bm25.mrr_at_k == 1.0


def test_benchmark_results_contain_both_retrieval_strategies():
    comparison = run_synthetic_benchmark(top_k=1)

    for query in comparison.queries:
        assert len(query.dense_results) == 1
        assert len(query.bm25_results) == 1
        assert query.dense_results[0].chunk_id in query.relevant_chunk_ids
        assert query.bm25_results[0].chunk_id in query.relevant_chunk_ids


def test_format_comparison_returns_markdown_table():
    comparison = run_synthetic_benchmark(top_k=1)

    output = format_comparison(comparison)

    assert "| Metric | Dense Search | BM25 |" in output
    assert "| Hit Rate@K |" in output
    assert "| Recall@K |" in output
    assert "| MRR@K |" in output
    assert "| Avg latency (ms) |" in output
