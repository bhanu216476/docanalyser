"""Benchmark generator and evaluator for 100-page synthetic document chunking comparison."""

import time
import math
from typing import Any, Optional
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.chunking.service import chunk_documents


def generate_synthetic_100_page_doc() -> list[Document]:
    """Generate a realistic 100-page synthetic research paper document list.

    Each page is intentionally an independent Document with its own page
    metadata. Therefore the 100-page benchmark naturally reports zero page
    crossings; a separate multi-page scenario is used to exercise that metric.

    Section structure:
    - Page 1: Introduction
    - Pages 2-10: Background
    - Pages 11-25: Related Work
    - Pages 26-45: Methodology
    - Pages 46-65: Experiments
    - Pages 66-85: Results
    - Pages 86-95: Discussion
    - Pages 96-100: Conclusion and References
    """
    sections = [
        (1, 1, "1. Introduction", "Introduction to Intent-Aware Adaptive Retrieval-Augmented Generation. Modern RAG systems must adaptively segment complex multi-domain technical documents while preserving fine-grained context and source alignment."),
        (2, 10, "2. Background & Related Work", "Background on document segmentation and vector representation. Classical fixed-window slicing often disrupts multi-sentence discourse structures, leading to semantic fragmentation."),
        (11, 25, "3. Related Literature", "Comprehensive survey of recursive splitting and semantic boundary detection mechanisms in high-dimensional text embeddings."),
        (26, 45, "4. Adaptive Chunking Methodology", "Detailed specification of hierarchical character splitting, semantic similarity thresholding, and metadata tracking across page boundaries."),
        (46, 65, "5. Experimental Evaluation", "Experimental setup across multi-page PDF corpora. We evaluate chunk granularity, page boundary preservation, and context retrieval precision."),
        (66, 85, "6. Empirical Results", "Quantitative metrics and comparative performance analysis across fixed, recursive, and semantic segmentation algorithms."),
        (86, 95, "7. Technical Discussion", "In-depth analysis of computational complexity, embedding call overhead, and optimal chunk parameter tuning for dense vector indexing."),
        (96, 100, "8. Conclusion and References", "Concluding remarks, future research directions, and academic citations for evidence-grounded multi-document question answering.")
    ]

    documents: list[Document] = []

    for start_p, end_p, section_title, section_text in sections:
        for p in range(start_p, end_p + 1):
            headings = [section_title] if p == start_p else []
            paragraphs = [
                f"{section_title} - Section Page {p} (Document Page {p}). {section_text}",
                f"Page {p} Paragraph 2: Technical analysis of evidence grounding in retrieval augmented generation pipelines. We maintain deterministic page indexing.",
                f"Page {p} Paragraph 3: Additional structural evidence and section details demonstrating page boundary tracking across large multi-page corpora."
            ]
            content = "\n\n".join(paragraphs)
            metadata = {
                "source": "synthetic_100_page_research_paper.pdf",
                "source_type": "pdf",
                "page": p - 1,
                "page_number": p,
                "document_id": "doc_synth_100p",
                "headings": headings
            }
            documents.append(Document(page_content=content, metadata=metadata))

    return documents


def evaluate_chunking_strategy(
    documents: list[Document],
    strategy: str,
    config: Optional[dict[str, Any]] = None,
    embedding_model: Optional[Embeddings] = None
) -> dict[str, Any]:
    """Execute a chunking strategy on document list and compute metrics.

    Metrics calculated:
    - total_chunks
    - avg_length
    - min_length
    - max_length
    - std_length
    - page_crossings: number of chunks covering more than one distinct source page
    - heading_chunks: number of chunks with non-empty preserved heading metadata
    - execution_time_ms
    - embedding_calls
    """
    start_time = time.perf_counter()
    chunks = chunk_documents(
        documents=documents,
        strategy=strategy,
        config=config,
        embedding_model=embedding_model
    )
    elapsed_time = (time.perf_counter() - start_time) * 1000.0  # ms

    if not chunks:
        return {
            "strategy": strategy,
            "total_chunks": 0,
            "avg_length": 0.0,
            "min_length": 0,
            "max_length": 0,
            "std_length": 0.0,
            "page_crossings": 0,
            "heading_chunks": 0,
            "execution_time_ms": round(elapsed_time, 2),
            "embedding_calls": getattr(embedding_model, "embed_call_count", "N/A") if embedding_model else "N/A"
        }

    lengths = [len(c.page_content) for c in chunks]
    total_chunks = len(chunks)
    avg_len = float(sum(lengths)) / total_chunks
    min_len = min(lengths)
    max_len = max(lengths)
    variance = sum((x - avg_len) ** 2 for x in lengths) / total_chunks
    std_len = math.sqrt(variance)

    # Page crossings check: check if chunk spans multiple page numbers
    page_crossings = 0
    heading_chunks = 0

    for c in chunks:
        meta = c.metadata
        page_nums = meta.get("page_numbers")
        if page_nums and len(set(page_nums)) > 1:
            page_crossings += 1
        headings = meta.get("headings", [])
        if headings:
            heading_chunks += 1

    emb_calls = "N/A"
    if hasattr(embedding_model, "embed_call_count"):
        emb_calls = getattr(embedding_model, "embed_call_count")

    return {
        "strategy": strategy,
        "total_chunks": total_chunks,
        "avg_length": round(avg_len, 2),
        "min_length": min_len,
        "max_length": max_len,
        "std_length": round(std_len, 2),
        "page_crossings": page_crossings,
        "heading_chunks": heading_chunks,
        "execution_time_ms": round(elapsed_time, 2),
        "embedding_calls": emb_calls
    }


def format_benchmark_table(results: list[dict[str, Any]]) -> str:
    """Format benchmark results into Markdown table."""
    headers = ["Strategy", "Chunks", "Avg Length", "Min", "Max", "Std Dev", "Page Crossings", "Heading Chunks", "Time (ms)", "Emb Calls"]
    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]
    for r in results:
        line = f"| {r['strategy'].capitalize()} | {r['total_chunks']} | {r['avg_length']} | {r['min_length']} | {r['max_length']} | {r['std_length']} | {r['page_crossings']} | {r['heading_chunks']} | {r['execution_time_ms']} | {r['embedding_calls']} |"
        table_lines.append(line)
    return "\n".join(table_lines)
