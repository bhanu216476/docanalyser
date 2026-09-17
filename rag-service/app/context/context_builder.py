"""
Core ContextBuilder orchestrator.

Transforms ranked retrieval/reranker results into a clean, token-bounded,
citation-ready context for prompt injection.
"""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Optional, Union

from app.core.config import settings
from app.retrieval.models import RetrievalResult
from app.reranking.models import RerankedResult
from app.context.models import (
    BuiltContext,
    Citation,
    ContextBuilderConfig,
    ContextChunk,
)
from app.context.token_budget import BudgetTracker, TiktokenCounter, TokenCounter
from app.context.deduplicator import deduplicate_results, is_valid_result
from app.context.citation import extract_citation, format_citation_id

logger = logging.getLogger(__name__)

CandidateType = Union[RetrievalResult, RerankedResult]


def format_context_block(
    citation_id: str,
    result: CandidateType,
    citation: Citation,
    include_metadata: bool = True,
    include_scores: bool = False,
) -> str:
    """
    Format a single evidence chunk into an LLM-ready block.

    Example format:
        [1]
        source: leave_policy.pdf
        page: 4

        Employees receive 12 casual leave days.
    """
    header_lines = [citation_id]

    if include_metadata:
        # Determine source representation (prefer file_name, fallback to source)
        src = citation.file_name or citation.source
        if src:
            header_lines.append(f"source: {src}")

        if citation.page_number is not None:
            header_lines.append(f"page: {citation.page_number}")

        if citation.section:
            header_lines.append(f"section: {citation.section}")

    if include_scores:
        score_parts: list[str] = []
        if isinstance(result, RerankedResult):
            score_parts.append(f"reranker_score: {result.reranker_score:.4f}")
            score_parts.append(f"retrieval_score: {result.retrieval_score:.4f}")
        elif isinstance(result, RetrievalResult):
            score_parts.append(f"score: {result.score:.4f}")

        if score_parts:
            header_lines.append(" | ".join(score_parts))

    header = "\n".join(header_lines)
    content = result.content.strip()

    return f"{header}\n\n{content}"


class ContextBuilder:
    """
    Converts ranked retrieval candidates into a clean, token-budgeted,
    citation-linked context for LLM generation.

    Responsibilities:
    1. Filter invalid candidate results.
    2. Deduplicate candidate evidence by chunk ID and normalized content.
    3. Respect configured token budget (including citation & metadata overhead).
    4. Preserve evidence ordering and score provenance.
    5. Assign sequential citation IDs ([1], [2], ...).
    6. Return a typed BuiltContext model.
    """

    def __init__(self, token_counter: Optional[TokenCounter] = None) -> None:
        """
        Initialize ContextBuilder with a pluggable token counter.

        Args:
            token_counter: Optional custom TokenCounter. Defaults to TiktokenCounter.
        """
        self.token_counter = token_counter or TiktokenCounter()

    def build(
        self,
        results: Sequence[CandidateType],
        config: Optional[ContextBuilderConfig] = None,
    ) -> BuiltContext:
        """
        Build an LLM-ready context from a ranked sequence of results.

        Args:
            results: Sequence of RetrievalResult or RerankedResult objects.
            config: Optional ContextBuilderConfig; uses system defaults if omitted.

        Returns:
            BuiltContext containing selected chunks, citations, text, and token metrics.
        """
        cfg = config or ContextBuilderConfig()
        total_budget = cfg.token_budget
        max_chunks = cfg.max_chunks

        # Handle empty or zero budget immediately
        if not results or total_budget <= 0:
            return BuiltContext(
                context_text="",
                selected_chunks=[],
                citations=[],
                token_count=0,
                token_budget=total_budget,
                dropped_chunks_count=len(results),
            )

        # Step 1 & 2: Deduplicate and filter invalid results while preserving rank
        candidates = deduplicate_results(
            results,
            deduplicate_content=cfg.deduplicate_content,
        )

        dropped_in_filtering = len(results) - len(candidates)
        selected_chunks: list[ContextChunk] = []
        citations: list[Citation] = []
        budget_tracker = BudgetTracker(
            token_budget=total_budget,
            token_counter=self.token_counter,
            separator="\n\n",
        )

        dropped_count = dropped_in_filtering

        # Step 3: Iterate candidates in rank order
        for candidate in candidates:
            # Check max_chunks limit
            if max_chunks is not None and len(selected_chunks) >= max_chunks:
                dropped_count += 1
                continue

            current_citation_index = len(selected_chunks) + 1
            citation_id = format_citation_id(current_citation_index)
            citation = extract_citation(candidate, citation_id)

            # Format candidate block
            formatted_text = format_context_block(
                citation_id=citation_id,
                result=candidate,
                citation=citation,
                include_metadata=cfg.include_metadata,
                include_scores=cfg.include_scores,
            )

            chunk_tokens = self.token_counter.count(formatted_text)

            # Check if chunk fits remaining budget
            if budget_tracker.can_fit(chunk_tokens):
                budget_tracker.add(chunk_tokens)
                retrieval_score = getattr(candidate, "retrieval_score", None)
                if retrieval_score is None and hasattr(candidate, "score"):
                    retrieval_score = candidate.score

                reranker_score = getattr(candidate, "reranker_score", None)

                selected_chunk = ContextChunk(
                    citation_id=citation_id,
                    chunk_id=candidate.chunk_id,
                    content=candidate.content,
                    formatted_text=formatted_text,
                    token_count=chunk_tokens,
                    final_rank=current_citation_index,
                    citation=citation,
                    retrieval_score=retrieval_score,
                    reranker_score=reranker_score,
                    metadata=dict(candidate.metadata),
                )
                selected_chunks.append(selected_chunk)
                citations.append(citation)
            else:
                # Chunk exceeds remaining budget
                if cfg.oversized_chunk_policy == "truncate":
                    # Attempt to safely truncate content to fit remaining budget
                    # Calculate overhead of header alone
                    header_block = format_context_block(
                        citation_id=citation_id,
                        result=candidate,
                        citation=citation,
                        include_metadata=cfg.include_metadata,
                        include_scores=cfg.include_scores,
                    ).split("\n\n")[0]

                    header_tokens = self.token_counter.count(header_block + "\n\n")
                    sep_tokens = (
                        budget_tracker.separator_tokens
                        if budget_tracker.item_count > 0
                        else 0
                    )
                    avail_for_content = (
                        budget_tracker.remaining_tokens - sep_tokens - header_tokens
                    )

                    if avail_for_content > 5:
                        # Simple proportional truncation heuristic for the content string
                        # Estimate chars based on token ratio
                        content_str = candidate.content.strip()
                        avg_ratio = max(1.0, len(content_str) / max(1, chunk_tokens))
                        target_len = int(avail_for_content * avg_ratio)
                        truncated_content = content_str[:target_len].rstrip() + "..."

                        # Re-format with truncated content
                        # Create a shallow temporary copy with truncated content
                        temp_formatted = f"{header_block}\n\n{truncated_content}"
                        trunc_tokens = self.token_counter.count(temp_formatted)

                        # Fine-tune if slightly over
                        while trunc_tokens > (avail_for_content + header_tokens) and len(truncated_content) > 10:
                            truncated_content = truncated_content[:-10].rstrip() + "..."
                            temp_formatted = f"{header_block}\n\n{truncated_content}"
                            trunc_tokens = self.token_counter.count(temp_formatted)

                        if budget_tracker.can_fit(trunc_tokens):
                            budget_tracker.add(trunc_tokens)
                            retrieval_score = getattr(candidate, "retrieval_score", None)
                            if retrieval_score is None and hasattr(candidate, "score"):
                                retrieval_score = candidate.score
                            reranker_score = getattr(candidate, "reranker_score", None)

                            selected_chunk = ContextChunk(
                                citation_id=citation_id,
                                chunk_id=candidate.chunk_id,
                                content=truncated_content,
                                formatted_text=temp_formatted,
                                token_count=trunc_tokens,
                                final_rank=current_citation_index,
                                citation=citation,
                                retrieval_score=retrieval_score,
                                reranker_score=reranker_score,
                                metadata=dict(candidate.metadata),
                            )
                            selected_chunks.append(selected_chunk)
                            citations.append(citation)
                            continue

                # Default / fallback: skip oversized chunk
                dropped_count += 1

        # Step 4: Assemble final context string
        context_text = "\n\n".join(chunk.formatted_text for chunk in selected_chunks)
        final_token_count = self.token_counter.count(context_text)

        # Log metadata only (safe data handling: no secrets or sensitive contents logged)
        logger.info(
            "Context built: selected_chunks=%d, token_count=%d, budget=%d, dropped=%d",
            len(selected_chunks),
            final_token_count,
            total_budget,
            dropped_count,
        )

        return BuiltContext(
            context_text=context_text,
            selected_chunks=selected_chunks,
            citations=citations,
            token_count=final_token_count,
            token_budget=total_budget,
            dropped_chunks_count=dropped_count,
        )
