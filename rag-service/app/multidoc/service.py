"""
Multi-Document Intelligence Service for DocAnalyser RAG Platform.
Orchestrates cross-document comparison, common theme extraction,
difference mapping, and contradiction/conflict detection.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.citations.models import GroundedCitation
from app.context.builder import ContextBuilder
from app.multidoc.models import (
    ComparisonDifference,
    DocumentConflict,
    MultiDocComparisonRequest,
    MultiDocComparisonResponse,
)
from app.retrieval.models import RetrievalFilter, RetrievalResult

logger = logging.getLogger(__name__)


class MultiDocumentIntelligenceService:
    """Provides deep cross-document analysis, comparisons, and conflict identification."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline

    def compare_documents(
        self,
        request: MultiDocComparisonRequest,
    ) -> MultiDocComparisonResponse:
        """
        Execute multi-document comparative analysis across specified document IDs.
        """
        doc_ids = request.document_ids
        query = request.query or "Compare the main topics, architecture, and differences across these documents."

        # 1. Retrieve candidates for each document independently to ensure balanced representation
        per_doc_chunks: dict[str, list[RetrievalResult]] = {}
        all_retrieved: list[RetrievalResult] = []

        for doc_id in doc_ids:
            try:
                # Query with specific document filter
                filt = RetrievalFilter(document_id=doc_id)
                res = self.pipeline.dense_retriever.retrieve(
                    query=query,
                    top_k=5,
                    filters=filt,
                )
                if not res:
                    # Fallback with file_name if document_id was passed as filename
                    filt_fn = RetrievalFilter(file_name=doc_id)
                    res = self.pipeline.dense_retriever.retrieve(
                        query=query,
                        top_k=5,
                        filters=filt_fn,
                    )
                per_doc_chunks[doc_id] = res
                all_retrieved.extend(res)
            except Exception as exc:
                logger.warning("Error retrieving chunks for doc '%s': %s", doc_id, exc)
                per_doc_chunks[doc_id] = []

        # If zero chunks found across all documents, attempt relaxed retrieval
        if not all_retrieved:
            try:
                all_retrieved = self.pipeline.dense_retriever.retrieve(
                    query=query,
                    top_k=8,
                    filters=None,
                )
            except Exception:
                all_retrieved = []

        # 2. Build structured comparative context
        builder = ContextBuilder(token_budget=4000)
        context = builder.build_context(all_retrieved)

        # 3. Formulate comparative prompt
        doc_names = list(per_doc_chunks.keys())
        prompt_text = (
            f"You are Maddy, an expert analytical AI. Conduct an objective comparative analysis "
            f"across the following documents: {', '.join(doc_names)}.\n\n"
            f"User Goal: {query}\n\n"
            f"Evidence Chunks from Documents:\n{context.context_text}\n\n"
            f"Please structure your response with:\n"
            f"1. Executive Consolidated Summary: A cohesive overview blending both documents.\n"
            f"2. Common Points & Agreements: Key shared principles or themes.\n"
            f"3. Key Contrasts & Differences: Specific dimensional differences.\n"
            f"4. Potential Inconsistencies or Conflicts: Any divergent or conflicting details.\n\n"
            f"Ground your answer strictly using citation markers [1], [2] referencing the evidence."
        )

        try:
            llm_response = self.pipeline.generate(
                prompt=prompt_text,
                temperature=0.4,
                max_tokens=1800,
            )
            raw_answer = llm_response.response_text
        except Exception as exc:
            logger.warning("LLM generation failed in multi-doc comparison: %s; using synthesis.", exc)
            raw_answer = self._generate_extractive_comparison(per_doc_chunks, query)

        # 4. Resolve Grounded Citations
        citations, _ = self.pipeline.citation_mapper.map_citations(
            answer=raw_answer,
            registry=context.citation_registry,
        )

        # 5. Extract structured differences and conflicts
        differences = self._parse_differences(raw_answer, doc_names)
        conflicts = self._parse_conflicts(raw_answer, doc_names)
        common_themes = self._parse_common_themes(raw_answer)
        matrix = self._build_comparison_matrix(differences, doc_names)

        compared_doc_meta = []
        for d_id in doc_ids:
            chunks = per_doc_chunks.get(d_id, [])
            fn = chunks[0].file_name if chunks and hasattr(chunks[0], "file_name") else d_id
            compared_doc_meta.append({"document_id": d_id, "file_name": fn})

        return MultiDocComparisonResponse(
            compared_documents=compared_doc_meta,
            consolidated_summary=raw_answer,
            common_themes=common_themes,
            differences=differences,
            conflicts=conflicts,
            comparison_matrix=matrix,
            citations=citations,
        )

    # --- Analysis Helpers ---

    @staticmethod
    def _parse_common_themes(text: str) -> list[str]:
        themes: list[str] = []
        # Find bullet points under Common Points
        matches = re.findall(r"(?:Common|Shared|Agreements)[\s\S]*?(?:Key Contrasts|Differences|$)", text, re.IGNORECASE)
        section = matches[0] if matches else text
        lines = [line.strip(" *-\t•") for line in section.split("\n") if line.strip().startswith(("*", "-", "•", "1.", "2."))]
        for line in lines[:5]:
            if len(line) >= 15:
                themes.append(line)
        return themes or ["Shared structural focus across ingested documents"]

    @staticmethod
    def _parse_differences(text: str, doc_names: list[str]) -> list[ComparisonDifference]:
        diffs: list[ComparisonDifference] = []
        matches = re.findall(r"(?:Contrasts|Differences)[\s\S]*?(?:Conflicts|Inconsistencies|$)", text, re.IGNORECASE)
        section = matches[0] if matches else ""
        lines = [line.strip(" *-\t•") for line in section.split("\n") if line.strip().startswith(("*", "-", "•", "1.", "2."))]
        for idx, line in enumerate(lines[:6]):
            if ":" in line:
                aspect, details = line.split(":", 1)
            else:
                aspect = f"Dimension {idx + 1}"
                details = line
            diffs.append(
                ComparisonDifference(
                    aspect=aspect.strip(),
                    document_positions={doc: details.strip() for doc in doc_names[:2]},
                    citations=[],
                )
            )
        return diffs

    @staticmethod
    def _parse_conflicts(text: str, doc_names: list[str]) -> list[DocumentConflict]:
        conflicts: list[DocumentConflict] = []
        matches = re.findall(r"(?:Inconsistencies|Conflicts|Discrepancies)[\s\S]*?$", text, re.IGNORECASE)
        section = matches[0] if matches else ""
        lines = [line.strip(" *-\t•") for line in section.split("\n") if line.strip().startswith(("*", "-", "•", "1.", "2."))]
        for idx, line in enumerate(lines[:4]):
            if "none" in line.lower() or "no direct conflict" in line.lower():
                continue
            conflicts.append(
                DocumentConflict(
                    topic=f"Discrepancy {idx + 1}",
                    description=line,
                    source_documents=doc_names[:2],
                    citations=[],
                )
            )
        return conflicts

    @staticmethod
    def _build_comparison_matrix(diffs: list[ComparisonDifference], doc_names: list[str]) -> dict[str, dict[str, str]]:
        matrix: dict[str, dict[str, str]] = {}
        for d in diffs:
            matrix[d.aspect] = d.document_positions
        return matrix

    @staticmethod
    def _generate_extractive_comparison(per_doc: dict[str, list[RetrievalResult]], query: str) -> str:
        parts: list[str] = [
            f"### Multi-Document Comparison: {query}\n",
            "#### Overview & Synthesized Evidence",
        ]
        citation_idx = 1
        for doc_id, chunks in per_doc.items():
            fn = chunks[0].file_name if chunks and hasattr(chunks[0], "file_name") else doc_id
            parts.append(f"\n**Document: {fn}**")
            for c in chunks[:2]:
                parts.append(f"- {c.content.strip()[:240]}... [{citation_idx}]")
                citation_idx += 1
        return "\n".join(parts)
