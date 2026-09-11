"""Benchmark test comparing Fixed, Recursive, and Semantic chunking on 100-page synthetic document."""

from langchain_core.documents import Document

from app.chunking.benchmark import (
    evaluate_chunking_strategy,
    format_benchmark_table,
    generate_synthetic_100_page_doc,
)
from app.chunking.service import chunk_documents
from tests.chunking.fake_embeddings import FakeEmbeddings


def test_fixed_and_recursive_have_different_structural_behavior():
    paragraphs = [
        "Alpha paragraph " + ("alpha-token " * 8),
        "Beta paragraph " + ("beta-token " * 8),
    ]
    text = "\n\n".join(paragraphs)
    document = Document(page_content=text, metadata={"source": "structure.txt"})

    fixed_chunks = chunk_documents(
        [document], strategy="fixed", config={"chunk_size": 70, "chunk_overlap": 0}
    )
    recursive_chunks = chunk_documents(
        [document], strategy="recursive", config={"chunk_size": 70, "chunk_overlap": 0}
    )

    assert fixed_chunks[0].page_content == text[:70]
    assert recursive_chunks[0].page_content != fixed_chunks[0].page_content
    assert [chunk.page_content for chunk in fixed_chunks] != [
        chunk.page_content for chunk in recursive_chunks
    ]


def test_semantic_uses_embeddings_and_semantic_boundaries():
    document = Document(
        page_content=(
            "Introduction topic. Introduction details. "
            "Results topic. Results details."
        ),
        metadata={"source": "semantic.txt"}
    )
    fake_embeddings = FakeEmbeddings()

    semantic_chunks = chunk_documents(
        [document],
        strategy="semantic",
        config={
            "breakpoint_threshold_type": "absolute",
            "breakpoint_threshold_amount": 0.5,
            "buffer_size": 0,
        },
        embedding_model=fake_embeddings,
    )
    fixed_chunks = chunk_documents(
        [document], strategy="fixed", config={"chunk_size": 1000, "chunk_overlap": 0}
    )

    assert fake_embeddings.embed_call_count == 1
    assert len(semantic_chunks) > 1
    assert semantic_chunks[0].metadata["chunking_strategy"] == "semantic"
    assert [chunk.page_content for chunk in semantic_chunks] != [
        chunk.page_content for chunk in fixed_chunks
    ]


def test_multi_page_chunk_crossing_and_metrics():
    document = Document(
        page_content="Page one content. Page two content.",
        metadata={
            "source": "multi-page.txt",
            "document_id": "multi-page",
            "page": 0,
            "page_number": 1,
            "page_numbers": [1, 2, 2],
            "headings": ["Multi-page section"],
        }
    )
    result = evaluate_chunking_strategy(
        documents=[document],
        strategy="fixed",
        config={"chunk_size": 1000, "chunk_overlap": 0},
    )

    assert result["total_chunks"] > 0
    assert result["avg_length"] > 0
    assert result["min_length"] <= result["avg_length"] <= result["max_length"]
    assert result["std_length"] >= 0
    assert result["page_crossings"] == 1
    assert result["heading_chunks"] == 1
    assert result["execution_time_ms"] >= 0
    assert result["embedding_calls"] == "N/A"


def test_100_page_chunking_comparison():
    documents = generate_synthetic_100_page_doc()
    assert len(documents) == 100
    assert {document.metadata["page_number"] for document in documents} == set(range(1, 101))
    assert all(document.metadata["source_type"] == "pdf" for document in documents)
    assert sum(bool(document.metadata["headings"]) for document in documents) == 8

    fake_emb = FakeEmbeddings()

    # 1. Fixed Chunking
    fixed_res = evaluate_chunking_strategy(
        documents=documents,
        strategy="fixed",
        config={"chunk_size": 1000, "chunk_overlap": 100}
    )

    # 2. Recursive Character Chunking
    recursive_res = evaluate_chunking_strategy(
        documents=documents,
        strategy="recursive",
        config={"chunk_size": 1000, "chunk_overlap": 100}
    )

    # 3. Semantic Chunking
    semantic_res = evaluate_chunking_strategy(
        documents=documents,
        strategy="semantic",
        config={"breakpoint_threshold_type": "percentile", "breakpoint_threshold_amount": 80.0},
        embedding_model=fake_emb
    )

    results = [fixed_res, recursive_res, semantic_res]
    table = format_benchmark_table(results)

    print("\n\n=== 100-PAGE SYNTHETIC DOCUMENT CHUNKING BENCHMARK RESULTS ===")
    print(table)
    print("===============================================================\n")

    for res in results:
        assert res["total_chunks"] > 0
        assert res["avg_length"] > 0
        assert res["min_length"] > 0
        assert res["max_length"] >= res["min_length"]
        assert res["std_length"] >= 0

    assert fake_emb.embed_call_count > 0
    assert semantic_res["embedding_calls"] == fake_emb.embed_call_count
    for result in results:
        assert set(result) == {
            "strategy",
            "total_chunks",
            "avg_length",
            "min_length",
            "max_length",
            "std_length",
            "page_crossings",
            "heading_chunks",
            "execution_time_ms",
            "embedding_calls",
        }
