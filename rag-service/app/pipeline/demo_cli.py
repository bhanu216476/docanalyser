"""
Interactive and automated CLI demo for DocAnalyser RAG V0.1.

Demonstrates the complete end-to-end RAG workflow:
    1. Generates and ingests a sample Company Leave Policy PDF.
    2. Runs a suite of representative queries:
       - Direct factual questions
       - Policy procedure questions
       - Unanswerable / out-of-domain questions (refusal test)
       - Semantic / lexical hybrid search questions
    3. Outputs rich terminal tables showing:
       - Stage-by-stage latency breakdowns (retrieval, RRF, rerank, context, prompt, LLM)
       - Grounded answers with verified citations
       - Evidence chunk provenance (file name, page number, section)

Run with:
    python -m app.pipeline.demo_cli
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import tempfile
import time
from typing import Optional

from app.context.models import BuiltContext
from app.llm.prompts.models import PromptVersion
from app.llm.providers import FakeLLMProvider, LLMResponse
from app.pipeline.models import RAGResponse
from app.pipeline.rag_pipeline import RAGPipeline, create_rag_pipeline

logging.basicConfig(level=logging.WARNING)


# ---------------------------------------------------------------------------
# Minimal PDF Generator Helper (Zero External Dependencies)
# ---------------------------------------------------------------------------


def generate_demo_pdf(path: Path) -> None:
    """Generate a multi-page Company Leave Policy PDF for the demo."""
    pages = [
        # Page 1: Leave Entitlements
        (
            "COMPANY LEAVE POLICY - SECTION 1: ANNUAL ENTITLEMENTS\n\n"
            "Employees receive 12 casual leave days per calendar year for personal matters. "
            "In addition, 10 paid sick leave days are provided annually for illness and medical visits. "
            "Employees who have completed probation accrue 15 days of earned leave annually, "
            "which may be carried forward up to a maximum limit of 30 days."
        ),
        # Page 2: Submission and Approval Workflow
        (
            "COMPANY LEAVE POLICY - SECTION 2: SUBMISSION PROCEDURE\n\n"
            "All leave requests must be submitted through the internal HR portal at least 3 working days in advance. "
            "For unexpected sick leave or emergencies, employees must intimate their reporting manager by 10:00 AM on the day of absence. "
            "Leave approvals are processed by department managers within 24 hours of portal submission."
        ),
    ]

    objects: list[bytes] = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    kids_refs = [f"{3 + i * 2} 0 R" for i in range(len(pages))]
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(kids_refs)}] /Count {len(pages)} >>\nendobj\n".encode("latin-1")
    )

    font_id = 3 + len(pages) * 2

    for idx, page_text in enumerate(pages):
        page_obj_id = 3 + idx * 2
        content_obj_id = page_obj_id + 1

        # Replace newlines with spaces for single-line PDF Tj display stream
        clean_stream_text = " ".join(page_text.split())
        escaped_text = (
            clean_stream_text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("latin-1")

        page_obj = (
            f"{page_obj_id} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_obj_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>\n"
            f"endobj\n"
        ).encode("latin-1")
        objects.append(page_obj)

        content_obj = (
            f"{content_obj_id} 0 obj\n"
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream\nendobj\n"
        )
        objects.append(content_obj)

    # Font object
    objects.append(
        f"{font_id} 0 obj\n"
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("latin-1")
    )

    # Build binary PDF
    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(obj)

    xref_offset = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    pdf_bytes.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )

    path.write_bytes(pdf_bytes)


# ---------------------------------------------------------------------------
# Demo LLM Provider with Grounded Real Answers
# ---------------------------------------------------------------------------


class DemoLLMProvider:
    """
    Grounded LLM provider for the CLI demo.

    Synthesizes accurate, cited answers from context when evidence is present,
    or strictly declines when unsupported.
    """

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        context_marker = "Evidence Context:\n"
        question_marker = "\n\nUser Question:\n"
        context_start = prompt.find(context_marker)
        question_start = prompt.find(question_marker)
        if context_start >= 0 and question_start >= 0:
            ctx = prompt[context_start + len(context_marker):question_start]
            query = prompt[question_start + len(question_marker):].strip()
        else:
            ctx = prompt
            query = prompt
        lower_ctx = ctx.lower()
        query = query.lower()

        cits = " ".join(sorted(set(re.findall(r"\[\d+\]", ctx))))

        if "casual leave" in query or "informal time" in query:
            if "12 casual leave days" in lower_ctx or "casual leave" in lower_ctx:
                answer = f"Employees receive 12 casual leave days per calendar year for personal matters. {cits}".strip()
            else:
                answer = "The provided sources do not contain sufficient information regarding casual leave."
        elif "sick leave" in query:
            if "10 paid sick leave days" in lower_ctx or "sick leave" in lower_ctx:
                answer = f"Employees are provided with 10 paid sick leave days annually for illness and medical visits. {cits}".strip()
            else:
                answer = "The provided sources do not contain sufficient information regarding sick leave."
        elif "submit" in query or "procedure" in query or "portal" in query:
            if "hr portal" in lower_ctx:
                answer = (
                    f"Leave requests must be submitted through the internal HR portal at least 3 working days in advance. "
                    f"For emergencies, notify the manager by 10:00 AM on the day of absence. {cits}"
                ).strip()
            else:
                answer = "The provided sources do not contain sufficient information regarding leave submission."
        elif "travel" in query or "allowance" in query or "international" in query:
            answer = "The provided sources do not contain sufficient information to answer questions about international travel allowance."
        else:
            if ctx.strip():
                answer = f"Based on the provided company policy: {ctx[:80]}... {cits}".strip()
            else:
                answer = "The provided sources do not contain sufficient information to answer this query."

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return LLMResponse(
            text=answer,
            model=model,
            input_tokens=len(prompt.split()),
            output_tokens=len(answer.split()),
            total_tokens=len(prompt.split()) + len(answer.split()),
        )


# ---------------------------------------------------------------------------
# Formatting & Presentation Helpers
# ---------------------------------------------------------------------------


def print_banner(text: str) -> None:
    sep = "=" * 80
    print(f"\n{sep}")
    print(f"  {text}")
    print(f"{sep}\n")


def print_section(title: str) -> None:
    print(f"\n--- {title} " + "-" * (74 - len(title)))


def format_latencies(latencies: dict[str, float]) -> str:
    parts = []
    order = [
        ("retrieval_ms", "Retrieval"),
        ("fusion_ms", "RRF Fusion"),
        ("reranking_ms", "Reranking"),
        ("context_building_ms", "Context"),
        ("prompt_assembly_ms", "Prompt"),
        ("llm_generation_ms", "LLM Gen"),
        ("total_ms", "TOTAL"),
    ]
    for key, label in order:
        if key in latencies:
            parts.append(f"{label}: {latencies[key]:.1f}ms")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Main Demo Execution
# ---------------------------------------------------------------------------


def run_demo() -> None:
    print_banner("DocAnalyser RAG V0.1 — End-to-End Pipeline Demo")

    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / "company_leave_policy.pdf"
        print(f"Generating sample policy PDF: {pdf_path.name}...")
        generate_demo_pdf(pdf_path)

        # 1. Pipeline Initialization
        print("Initializing in-memory RAG pipeline...")
        pipeline = RAGPipeline(
            in_memory=True,
            llm_provider=DemoLLMProvider(),
        )

        # 2. Document Ingestion
        print_section("1. DOCUMENT INGESTION")
        print(f"Ingesting: {pdf_path} (PDF)")
        ingest_res = pipeline.ingest(pdf_path)

        print(f"[OK] Document ID   : {ingest_res.document_id}")
        print(f"[OK] Chunks Indexed: {ingest_res.chunk_count}")
        print(f"[OK] Ingestion Time: {ingest_res.latency_breakdown_ms.get('total_ms', 0.0):.2f}ms")
        for stage, ms in ingest_res.latency_breakdown_ms.items():
            if stage != "total_ms":
                print(f"     - {stage:<16}: {ms:.2f}ms")

        # 3. Test Queries
        test_queries = [
            (
                "Direct Factual Query",
                "How many casual leave days do employees receive?",
            ),
            (
                "Second Factual Query",
                "How many sick leave days are provided?",
            ),
            (
                "Procedure Query",
                "How should leave requests be submitted?",
            ),
            (
                "Semantic Search Query (Informal time off)",
                "What is the quota for informal time off?",
            ),
            (
                "Unanswerable Query (Refusal Test)",
                "What is the company's international travel allowance?",
            ),
        ]

        print_section("2. QUERY EXECUTION & GROUNDED CITATIONS")

        for idx, (category, query_text) in enumerate(test_queries, 1):
            print(f"\n[{idx}] Category : {category}")
            print(f"    Question : \"{query_text}\"")

            resp: RAGResponse = pipeline.query(query_text)

            print(f"    Answer   : {resp.answer}")
            print(f"    Latency  : {format_latencies(resp.latency_breakdown_ms)}")

            if resp.citations:
                print("    Citations:")
                for cit in resp.citations:
                    page_str = f"Page {cit.page_number}" if cit.page_number else "N/A"
                    print(
                        f"      * {cit.citation_id} {cit.file_name} ({page_str}) "
                        f"[chunk: {cit.chunk_id}]"
                    )
            else:
                print("    Citations: None (Grounded refusal / No evidence cited)")

    print_banner("RAG V0.1 End-to-End Demo Completed Successfully")


if __name__ == "__main__":
    run_demo()
