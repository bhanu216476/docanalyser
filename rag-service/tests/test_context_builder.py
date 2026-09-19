"""
Comprehensive unit, integration, and edge-case tests for the Context Builder module.
"""

from __future__ import annotations

import pytest
from app.context.models import (
    BuiltContext,
    Citation,
    ContextBuilderConfig,
    ContextChunk,
)
from app.context.token_budget import (
    BudgetTracker,
    DeterministicCharRatioTokenCounter,
    TiktokenCounter,
    TokenCounter,
    WhitespaceTokenCounter,
)
from app.context.citation import extract_citation, format_citation_id
from app.context.deduplicator import (
    deduplicate_results,
    is_valid_result,
    normalize_content_for_dedup,
)
from app.context.context_builder import ContextBuilder, format_context_block
from app.retrieval.models import RetrievalProvenance, RetrievalResult
from app.reranking.models import RerankedResult


class MockDeterministicTokenCounter:
    """Fixed word/token counter for predictable unit tests."""

    def count(self, text: str) -> int:
        if not text:
            return 0
        # Return count of whitespace-separated tokens + newline tokens
        words = [w for w in text.replace("\n", " <NL> ").split() if w]
        return len(words)


def create_retrieval_result(
    chunk_id: str,
    content: str,
    score: float = 0.85,
    rank: int = 1,
    source: str = "leave_policy.pdf",
    page_number: int | None = 4,
    file_name: str | None = None,
    file_type: str = "pdf",
    document_id: str = "doc_leave_123",
    section: str | None = None,
    metadata: dict | None = None,
) -> RetrievalResult:
    f_name = file_name or (source.split("/")[-1].split("\\")[-1] if source else "")
    provenance = RetrievalProvenance(
        chunk_id=chunk_id,
        document_id=document_id,
        page_number=page_number,
        source=source,
        file_type=file_type,
    )
    return RetrievalResult(
        chunk_id=chunk_id,
        content=content,
        score=score,
        rank=rank,
        source=source,
        file_name=f_name,
        file_type=file_type,
        document_id=document_id,
        section=section,
        provenance=provenance,
        metadata=metadata or {},
    )


def create_reranked_result(
    chunk_id: str,
    content: str,
    reranker_score: float = 0.95,
    retrieval_score: float = 0.70,
    retrieval_rank: int = 2,
    reranked_rank: int = 1,
    source: str = "hr_policy.pdf",
    page_number: int | None = 8,
    file_name: str = "hr_policy.pdf",
    file_type: str = "pdf",
    document_id: str = "doc_hr_456",
    section: str | None = "Portal",
    metadata: dict | None = None,
) -> RerankedResult:
    provenance = RetrievalProvenance(
        chunk_id=chunk_id,
        document_id=document_id,
        page_number=page_number,
        source=source,
        file_type=file_type,
    )
    return RerankedResult(
        chunk_id=chunk_id,
        content=content,
        retrieval_score=retrieval_score,
        reranker_score=reranker_score,
        retrieval_rank=retrieval_rank,
        reranked_rank=reranked_rank,
        rank_delta=retrieval_rank - reranked_rank,
        source=source,
        file_name=file_name,
        file_type=file_type,
        document_id=document_id,
        section=section,
        provenance=provenance,
        metadata=metadata or {},
    )


# --------------------------------------------------------------------------
# 1. Selection & Ordering Tests
# --------------------------------------------------------------------------

def test_selection_preserves_ranked_order():
    """Context Builder evaluates and includes chunks in their original rank order."""
    r1 = create_retrieval_result("chunk-C", "Content for C", rank=1)
    r2 = create_retrieval_result("chunk-A", "Content for A", rank=2)
    r3 = create_retrieval_result("chunk-B", "Content for B", rank=3)

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=1000)

    built = builder.build([r1, r2, r3], config=config)

    assert len(built.selected_chunks) == 3
    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-C", "chunk-A", "chunk-B"]
    assert [c.final_rank for c in built.selected_chunks] == [1, 2, 3]
    assert [c.citation_id for c in built.selected_chunks] == ["[1]", "[2]", "[3]"]


def test_selection_respects_max_chunks():
    """Selection stops when max_chunks is reached, even if budget remains."""
    results = [
        create_retrieval_result(f"chunk-{i}", f"Short content {i}", rank=i)
        for i in range(1, 10)
    ]

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=5000, max_chunks=3)

    built = builder.build(results, config=config)

    assert len(built.selected_chunks) == 3
    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-1", "chunk-2", "chunk-3"]
    assert built.dropped_chunks_count == 6


# --------------------------------------------------------------------------
# 2. Duplicate Removal Tests
# --------------------------------------------------------------------------

def test_deduplication_by_chunk_id():
    """Duplicate chunk IDs (e.g. A, B, A, C) are eliminated while preserving first occurrence."""
    r_a1 = create_retrieval_result("chunk-A", "First copy of chunk A", rank=1)
    r_b = create_retrieval_result("chunk-B", "Content of chunk B", rank=2)
    r_a2 = create_retrieval_result("chunk-A", "Second copy of chunk A with diff text", rank=3)
    r_c = create_retrieval_result("chunk-C", "Content of chunk C", rank=4)

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=1000)

    built = builder.build([r_a1, r_b, r_a2, r_c], config=config)

    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-A", "chunk-B", "chunk-C"]
    assert built.selected_chunks[0].content == "First copy of chunk A"
    assert len(built.citations) == 3
    assert [cit.citation_id for cit in built.citations] == ["[1]", "[2]", "[3]"]


def test_deduplication_by_normalized_content():
    """Different chunk IDs with identical normalized text are deduplicated."""
    r1 = create_retrieval_result("chunk-1", "Employees receive 12 casual leave days.", rank=1)
    r2 = create_retrieval_result("chunk-2", "Employees   receive 12  casual leave days.  \n", rank=2)
    r3 = create_retrieval_result("chunk-3", "Leave requests must be submitted through portal.", rank=3)

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=1000, deduplicate_content=True)

    built = builder.build([r1, r2, r3], config=config)

    assert len(built.selected_chunks) == 2
    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-1", "chunk-3"]


def test_deduplicate_content_can_be_disabled():
    """When deduplicate_content is False, distinct IDs with same content are both preserved."""
    r1 = create_retrieval_result("chunk-1", "Identical text.", rank=1)
    r2 = create_retrieval_result("chunk-2", "Identical text.", rank=2)

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=1000, deduplicate_content=False)

    built = builder.build([r1, r2], config=config)

    assert len(built.selected_chunks) == 2
    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-1", "chunk-2"]


# --------------------------------------------------------------------------
# 3. Token Budget & Overhead Tests
# --------------------------------------------------------------------------

def test_token_budget_enforcement():
    """Assembled context strictly stays within the configured token budget."""
    counter = WhitespaceTokenCounter()
    builder = ContextBuilder(token_counter=counter)

    # Each chunk text is ~20 words. Plus header overhead (~6 words).
    # Total per chunk ~ 26 words. With separators (\n\n = 0 words in whitespace split, or 2 in full tokenizers).
    chunks = [
        create_retrieval_result(f"chunk-{i}", f"This is chunk number {i} providing specific evidence details about policy rules.", rank=i)
        for i in range(1, 15)
    ]

    # Let's set budget to accommodate roughly 3 chunks
    config = ContextBuilderConfig(token_budget=60, max_chunks=None)
    built = builder.build(chunks, config=config)

    assert built.token_count <= 60
    assert len(built.selected_chunks) > 0
    assert built.token_budget == 60
    assert counter.count(built.context_text) == built.token_count


def test_token_budget_accounts_for_formatting_and_citations():
    """Formatting overhead (citation ID, metadata, delimiters) is counted against budget."""
    counter = MockDeterministicTokenCounter()
    builder = ContextBuilder(token_counter=counter)

    r1 = create_retrieval_result(
        "chunk-1",
        "Short content",
        source="policy.pdf",
        page_number=1,
        section="Intro",
    )

    # Format standalone block
    cit = extract_citation(r1, "[1]")
    block = format_context_block("[1]", r1, cit, include_metadata=True)
    block_tokens = counter.count(block)

    # Budget exactly matching block tokens should succeed
    built_exact = builder.build([r1], config=ContextBuilderConfig(token_budget=block_tokens))
    assert len(built_exact.selected_chunks) == 1

    # Budget 1 token less should fail (skip)
    built_under = builder.build([r1], config=ContextBuilderConfig(token_budget=block_tokens - 1))
    assert len(built_under.selected_chunks) == 0
    assert built_under.context_text == ""


# --------------------------------------------------------------------------
# 4. Oversized Chunk Policy Tests
# --------------------------------------------------------------------------

def test_oversized_chunk_skipped_by_default():
    """Default policy skips a chunk that exceeds remaining budget without exceeding limit."""
    counter = WhitespaceTokenCounter()
    builder = ContextBuilder(token_counter=counter)

    # Chunk 1: small (~10 words)
    r1 = create_retrieval_result("chunk-1", "Short snippet of text.", rank=1)
    # Chunk 2: large (100 words)
    r2 = create_retrieval_result("chunk-2", "word " * 100, rank=2)
    # Chunk 3: small (~10 words)
    r3 = create_retrieval_result("chunk-3", "Another small snippet.", rank=3)

    # Budget enough for r1 and r3, but not r2
    config = ContextBuilderConfig(token_budget=40, oversized_chunk_policy="skip")
    built = builder.build([r1, r2, r3], config=config)

    assert built.token_count <= 40
    assert [c.chunk_id for c in built.selected_chunks] == ["chunk-1", "chunk-3"]
    # Chunk 3 should be citation [2] since chunk 2 was skipped
    assert built.selected_chunks[1].citation_id == "[2]"


def test_oversized_chunk_truncate_policy():
    """When oversized_chunk_policy='truncate', chunk is safely truncated to fit budget."""
    counter = WhitespaceTokenCounter()
    builder = ContextBuilder(token_counter=counter)

    r1 = create_retrieval_result("chunk-1", "word " * 50, rank=1)
    config = ContextBuilderConfig(token_budget=20, oversized_chunk_policy="truncate")

    built = builder.build([r1], config=config)

    assert built.token_count <= 20
    assert len(built.selected_chunks) == 1
    assert "..." in built.selected_chunks[0].content


# --------------------------------------------------------------------------
# 5. Metadata & Score Preservation Tests
# --------------------------------------------------------------------------

def test_metadata_preservation_and_no_fabrication():
    """Verifies all present metadata fields are retained and missing fields are NOT fabricated."""
    # Chunk with known page and section
    r1 = create_retrieval_result(
        "chunk-1",
        "Content 1",
        source="doc1.pdf",
        page_number=5,
        section="Sec 1",
        document_id="doc-A",
        file_name="doc1.pdf",
        file_type="pdf",
    )
    # Chunk with missing page and missing section
    r2 = create_retrieval_result(
        "chunk-2",
        "Content 2",
        source="doc2.txt",
        page_number=None,
        section=None,
        document_id="doc-B",
        file_name="doc2.txt",
        file_type="txt",
    )

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    built = builder.build([r1, r2], config=ContextBuilderConfig(token_budget=1000))

    c1 = built.citations[0]
    assert c1.source == "doc1.pdf"
    assert c1.page_number == 5
    assert c1.section == "Sec 1"
    assert c1.document_id == "doc-A"

    c2 = built.citations[1]
    assert c2.source == "doc2.txt"
    assert c2.page_number is None
    assert c2.section is None
    assert "page:" not in built.selected_chunks[1].formatted_text


def test_score_preservation_with_reranked_results():
    """Context preserves both retrieval_score and reranker_score from RerankedResult."""
    rr = create_reranked_result(
        "chunk-reranked",
        "Reranked evidence text.",
        reranker_score=0.9876,
        retrieval_score=0.6543,
        retrieval_rank=3,
        reranked_rank=1,
    )

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    config = ContextBuilderConfig(token_budget=1000, include_scores=True)
    built = builder.build([rr], config=config)

    item = built.selected_chunks[0]
    assert item.reranker_score == 0.9876
    assert item.retrieval_score == 0.6543
    assert "reranker_score: 0.9876" in item.formatted_text
    assert "retrieval_score: 0.6543" in item.formatted_text


# --------------------------------------------------------------------------
# 6. Budget Edge Cases Tests
# --------------------------------------------------------------------------

def test_budget_zero():
    """token_budget=0 returns an empty context."""
    r1 = create_retrieval_result("chunk-1", "Some content")
    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    built = builder.build([r1], config=ContextBuilderConfig(token_budget=0))

    assert built.context_text == ""
    assert built.selected_chunks == []
    assert built.citations == []
    assert built.token_count == 0
    assert built.token_budget == 0


def test_all_chunks_exceed_budget():
    """When all chunks exceed budget, empty context is returned."""
    r1 = create_retrieval_result("chunk-1", "A " * 50)
    r2 = create_retrieval_result("chunk-2", "B " * 50)

    builder = ContextBuilder(token_counter=WhitespaceTokenCounter())
    built = builder.build([r1, r2], config=ContextBuilderConfig(token_budget=5))

    assert built.context_text == ""
    assert len(built.selected_chunks) == 0
    assert built.dropped_chunks_count == 2


def test_empty_results_input():
    """Empty results list returns a valid empty BuiltContext."""
    builder = ContextBuilder()
    built = builder.build([])

    assert built.context_text == ""
    assert built.selected_chunks == []
    assert built.citations == []
    assert built.token_count == 0


# --------------------------------------------------------------------------
# 7. Invalid Results Handling
# --------------------------------------------------------------------------

def test_invalid_and_malformed_results_skipped():
    """Malformed chunks (blank chunk_id or whitespace content) are skipped without error."""
    valid_1 = create_retrieval_result("valid-1", "Good evidence 1", rank=1)
    empty_content = create_retrieval_result("bad-1", "   \n\t  ", rank=2)
    empty_id = create_retrieval_result("   ", "Good evidence 2", rank=3)
    valid_2 = create_retrieval_result("valid-2", "Good evidence 3", rank=4)

    builder = ContextBuilder(token_counter=MockDeterministicTokenCounter())
    built = builder.build([valid_1, empty_content, empty_id, valid_2], config=ContextBuilderConfig(token_budget=1000))

    assert [c.chunk_id for c in built.selected_chunks] == ["valid-1", "valid-2"]
    assert [c.citation_id for c in built.selected_chunks] == ["[1]", "[2]"]


# --------------------------------------------------------------------------
# 8. Determinism Test
# --------------------------------------------------------------------------

def test_determinism_across_repeated_runs():
    """Executing build multiple times on identical input produces strictly identical results."""
    results = [
        create_retrieval_result("c1", "Content 1", rank=1, source="doc.pdf", page_number=2),
        create_retrieval_result("c2", "Content 2", rank=2, source="doc.pdf", page_number=3),
        create_retrieval_result("c1", "Duplicate 1", rank=3),
        create_retrieval_result("c3", "Content 3", rank=4, source="doc.pdf", page_number=4),
    ]

    builder = ContextBuilder(token_counter=WhitespaceTokenCounter())
    config = ContextBuilderConfig(token_budget=200)

    out1 = builder.build(results, config=config)
    out2 = builder.build(results, config=config)

    assert out1.context_text == out2.context_text
    assert out1.token_count == out2.token_count
    assert [c.chunk_id for c in out1.selected_chunks] == [c.chunk_id for c in out2.selected_chunks]
    assert [c.citation_id for c in out1.selected_chunks] == [c.citation_id for c in out2.selected_chunks]


# --------------------------------------------------------------------------
# 9. TokenCounter Protocol & Counter Implementations
# --------------------------------------------------------------------------

def test_token_counter_implementations():
    """Verify TokenCounter implementations conform to the protocol."""
    assert isinstance(WhitespaceTokenCounter(), TokenCounter)
    assert isinstance(DeterministicCharRatioTokenCounter(), TokenCounter)
    assert isinstance(TiktokenCounter(), TokenCounter)

    ws = WhitespaceTokenCounter()
    assert ws.count("hello world") == 2
    assert ws.count("") == 0

    char_counter = DeterministicCharRatioTokenCounter(chars_per_token=4)
    assert char_counter.count("1234") == 1
    assert char_counter.count("12345") == 2
    assert char_counter.count("") == 0

    tik = TiktokenCounter()
    assert tik.count("hello world") >= 2
    assert tik.count("") == 0


# --------------------------------------------------------------------------
# 10. End-to-End Test (Leave Policy Example from Spec)
# --------------------------------------------------------------------------

def test_end_to_end_leave_policy_use_case():
    """
    Day 12 End-to-End Leave Policy Specification Test:
    Query: 'How many casual leave days?'
    Rank 1: leave_policy.pdf, p.4, 'Employees receive 12 casual leave days.'
    Rank 2: hr_policy.pdf, p.8, 'Leave requests must be submitted through the HR portal.'
    Rank 3: leave_policy.pdf, p.4, 'Employees receive 12 casual leave days.' (Duplicate)
    Rank 4: employee_handbook.pdf, p.12, 'Handbook introduction content.'
    """
    r1 = create_retrieval_result(
        chunk_id="chunk-leave-p4",
        content="Employees receive 12 casual leave days.",
        source="leave_policy.pdf",
        page_number=4,
        rank=1,
    )
    r2 = create_retrieval_result(
        chunk_id="chunk-hr-p8",
        content="Leave requests must be submitted through the HR portal.",
        source="hr_policy.pdf",
        page_number=8,
        rank=2,
    )
    r3 = create_retrieval_result(
        chunk_id="chunk-leave-p4",  # Duplicate ID and duplicate content
        content="Employees receive 12 casual leave days.",
        source="leave_policy.pdf",
        page_number=4,
        rank=3,
    )
    r4 = create_retrieval_result(
        chunk_id="chunk-handbook-p12",
        content="Handbook introduction content.",
        source="employee_handbook.pdf",
        page_number=12,
        rank=4,
    )

    builder = ContextBuilder(token_counter=WhitespaceTokenCounter())
    config = ContextBuilderConfig(token_budget=500)

    built = builder.build([r1, r2, r3, r4], config=config)

    # 1. Deduplication verified: exactly 3 unique chunks selected
    assert len(built.selected_chunks) == 3
    assert [c.chunk_id for c in built.selected_chunks] == [
        "chunk-leave-p4",
        "chunk-hr-p8",
        "chunk-handbook-p12",
    ]

    # 2. Sequential citations verified
    assert [c.citation_id for c in built.selected_chunks] == ["[1]", "[2]", "[3]"]
    assert [cit.citation_id for cit in built.citations] == ["[1]", "[2]", "[3]"]

    # 3. Source metadata formatting verified
    expected_block_1 = (
        "[1]\n"
        "source: leave_policy.pdf\n"
        "page: 4\n\n"
        "Employees receive 12 casual leave days."
    )
    expected_block_2 = (
        "[2]\n"
        "source: hr_policy.pdf\n"
        "page: 8\n\n"
        "Leave requests must be submitted through the HR portal."
    )
    expected_block_3 = (
        "[3]\n"
        "source: employee_handbook.pdf\n"
        "page: 12\n\n"
        "Handbook introduction content."
    )

    assert built.selected_chunks[0].formatted_text == expected_block_1
    assert built.selected_chunks[1].formatted_text == expected_block_2
    assert built.selected_chunks[2].formatted_text == expected_block_3

    assert built.context_text == f"{expected_block_1}\n\n{expected_block_2}\n\n{expected_block_3}"
    assert built.token_count <= 500
    assert built.dropped_chunks_count == 1  # 1 duplicate dropped
