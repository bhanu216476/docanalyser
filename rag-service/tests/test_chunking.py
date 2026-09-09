"""
Tests for document chunking: Fixed-size and Recursive/Structure-aware.

Covers:
    - FixedSizeChunker edge cases, validation, overlap, and deterministic IDs.
    - RecursiveChunker paragraph preservation, Markdown headings, nested sections,
      oversized sections, empty sections, and character fallback.
    - Property and invariant testing.
    - Strategy comparison demo between FixedSizeChunker and RecursiveChunker.
"""

import pytest
from pydantic import ValidationError

from app.ingestion.chunking import (
    BaseChunker,
    Chunk,
    FixedSizeChunker,
    RecursiveChunker,
)
from app.ingestion.models import Document


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def make_document():
    """Helper factory fixture to construct test Document instances."""
    def _factory(
        content: str,
        file_name: str = "test.md",
        file_type: str = "md",
        source: str = "/workspace/test.md",
        metadata: dict | None = None,
    ) -> Document:
        return Document(
            content=content,
            file_name=file_name,
            file_type=file_type,
            source=source,
            metadata=metadata or {},
        )
    return _factory


# ======================================================================
# Section 13: Fixed-Size Chunker Tests
# ======================================================================

class TestFixedSizeChunker:
    """Test suite for FixedSizeChunker."""

    def test_empty_document(self, make_document):
        """Test 1: Empty or whitespace-only document returns no chunks."""
        chunker = FixedSizeChunker(chunk_size=100, overlap=20)

        # Empty string
        doc_empty = make_document("")
        assert chunker.chunk(doc_empty) == []

        # Whitespace-only string
        doc_whitespace = make_document("   \n\n  \t  ")
        assert chunker.chunk(doc_whitespace) == []

    def test_document_smaller_than_chunk_size(self, make_document):
        """Test 2: Document smaller than chunk_size returns exactly 1 chunk."""
        chunker = FixedSizeChunker(chunk_size=100, overlap=20)
        doc = make_document("Short text well under 100 characters.")

        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].content == "Short text well under 100 characters."
        assert chunks[0].chunk_index == 0
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(doc.content)

    def test_document_exactly_equal_to_chunk_size(self, make_document):
        """Test 3: Document exactly equal to chunk_size returns exactly 1 chunk."""
        chunk_size = 50
        content = "A" * chunk_size
        doc = make_document(content)

        chunker = FixedSizeChunker(chunk_size=chunk_size, overlap=10)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 1
        assert chunks[0].content == content
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_count == chunk_size

    def test_large_document_progression_and_ordering(self, make_document):
        """Test 4: Large document produces multiple ordered, non-empty chunks."""
        content = "0123456789" * 30  # 300 characters
        doc = make_document(content)

        chunker = FixedSizeChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(doc)

        assert len(chunks) > 1
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert chunk.char_count <= 100
            assert len(chunk.content.strip()) > 0
            assert chunk.start_char is not None
            assert chunk.end_char is not None
            assert chunk.start_char <= chunk.end_char

    def test_overlap_content(self, make_document):
        """Test 5: Verify that configured overlapping content is present across chunks."""
        # 10 chars: "0123456789"
        # chunk_size=6, overlap=2, step=4
        # Chunk 0: "012345" (chars 0..6)
        # Chunk 1: "456789" (chars 4..10)
        # Overlap content is "45" (length 2)
        content = "0123456789"
        doc = make_document(content)

        chunker = FixedSizeChunker(chunk_size=6, overlap=2)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 2
        assert chunks[0].content == "012345"
        assert chunks[1].content == "456789"

        # Overlapping suffix of chunk 0 matches prefix of chunk 1
        overlap_len = 2
        assert chunks[0].content[-overlap_len:] == chunks[1].content[:overlap_len]

    def test_invalid_chunk_size_rejected(self):
        """Test 6: Invalid chunk_size <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            FixedSizeChunker(chunk_size=0, overlap=0)

        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            FixedSizeChunker(chunk_size=-10, overlap=0)

    def test_invalid_overlap_rejected(self):
        """Test 7: Invalid overlap (overlap >= chunk_size or overlap < 0) raises ValueError."""
        # overlap equal to chunk_size
        with pytest.raises(ValueError, match="strictly less than chunk_size"):
            FixedSizeChunker(chunk_size=100, overlap=100)

        # overlap greater than chunk_size
        with pytest.raises(ValueError, match="strictly less than chunk_size"):
            FixedSizeChunker(chunk_size=100, overlap=120)

        # negative overlap
        with pytest.raises(ValueError, match="non-negative integer"):
            FixedSizeChunker(chunk_size=100, overlap=-5)

    def test_deterministic_ids_and_indexes(self, make_document):
        """Test 8: Verify deterministic ordering, indexes, and chunk IDs."""
        content = "Predictable content for testing deterministic chunk IDs across runs."
        doc = make_document(content, metadata={"document_id": "doc-uuid-123"})

        chunker = FixedSizeChunker(chunk_size=30, overlap=10)
        chunks_run_1 = chunker.chunk(doc)
        chunks_run_2 = chunker.chunk(doc)

        assert len(chunks_run_1) == len(chunks_run_2)
        for c1, c2 in zip(chunks_run_1, chunks_run_2):
            assert c1.chunk_id == c2.chunk_id
            assert c1.chunk_id == f"doc-uuid-123:{c1.chunk_index}"
            assert c1.document_id == "doc-uuid-123"
            assert c1.content == c2.content


# ======================================================================
# Section 14: Recursive Chunker Tests
# ======================================================================

class TestRecursiveChunker:
    """Test suite for RecursiveChunker."""

    def test_paragraph_boundaries_preferred(self, make_document):
        """Test 1: Paragraphs are preferred over arbitrary character cuts."""
        p1 = "First paragraph containing a coherent thought about system architecture."
        p2 = "Second paragraph explaining the database ingestion pipeline design."
        p3 = "Third paragraph discussing retrieval and ranking methods."
        content = f"{p1}\n\n{p2}\n\n{p3}"
        doc = make_document(content, file_type="txt")

        # Set chunk_size large enough for each individual paragraph but too small for two combined
        chunk_size = 90
        chunker = RecursiveChunker(chunk_size=chunk_size, overlap=0)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 3
        assert chunks[0].content == p1
        assert chunks[1].content == p2
        assert chunks[2].content == p3

    def test_markdown_headings_respected(self, make_document):
        """Test 2: Markdown structural boundaries are respected.

        ## Installation and ## Usage are h2 headings nested under # Introduction.
        The recursive chunker tracks the full heading breadcrumb hierarchy,
        so their 'headings' metadata correctly includes the parent heading.
        """
        content = (
            "# Introduction\n\n"
            "This project provides a production-oriented RAG system.\n\n"
            "## Installation\n\n"
            "Run pip install -r requirements.txt to set up the environment.\n\n"
            "## Usage\n\n"
            "Invoke the chunker via the BaseChunker interface."
        )
        doc = make_document(content, file_type="md")

        chunker = RecursiveChunker(chunk_size=200, overlap=0)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 3

        # Chunk 0: # Introduction body
        assert "Introduction" in chunks[0].content
        assert chunks[0].metadata.get("headings") == ["Introduction"]
        assert chunks[0].metadata.get("section") == "Introduction"

        # Chunk 1: ## Installation is nested under # Introduction
        # The heading stack retains the parent, giving full hierarchy breadcrumb.
        assert "Installation" in chunks[1].content
        assert chunks[1].metadata.get("headings") == ["Introduction", "Installation"]
        assert chunks[1].metadata.get("section") == "Introduction > Installation"

        # Chunk 2: ## Usage is also nested under # Introduction
        assert "Usage" in chunks[2].content
        assert chunks[2].metadata.get("headings") == ["Introduction", "Usage"]
        assert chunks[2].metadata.get("section") == "Introduction > Usage"

    def test_oversized_section_splits_recursively(self, make_document):
        """Test 3: Oversized section is recursively split down separator hierarchy."""
        long_paragraph = "Sentence one of long section. " * 20  # ~600 chars
        content = f"# Large Section\n\n{long_paragraph}"
        doc = make_document(content, file_type="md")

        chunker = RecursiveChunker(chunk_size=150, overlap=20)
        chunks = chunker.chunk(doc)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.char_count <= 150
            # All chunks retain the parent section heading
            assert chunk.metadata.get("headings") == ["Large Section"]
            assert chunk.metadata.get("section") == "Large Section"

    def test_nested_sections_preserve_hierarchy_context(self, make_document):
        """Test 4: Nested sections preserve heading breadcrumbs in metadata."""
        content = (
            "# Company Policies\n\n"
            "## Leave Policy\n\n"
            "Employees receive 20 days annual paid leave.\n\n"
            "## Remote Work\n\n"
            "Employees may work remotely up to 2 days per week."
        )
        doc = make_document(content, file_type="md")

        chunker = RecursiveChunker(chunk_size=200, overlap=0)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 2
        # First chunk: Company Policies -> Leave Policy
        assert chunks[0].metadata.get("headings") == ["Company Policies", "Leave Policy"]
        assert chunks[0].metadata.get("section") == "Company Policies > Leave Policy"
        assert "20 days annual paid leave" in chunks[0].content

        # Second chunk: Company Policies -> Remote Work
        assert chunks[1].metadata.get("headings") == ["Company Policies", "Remote Work"]
        assert chunks[1].metadata.get("section") == "Company Policies > Remote Work"
        assert "remotely up to 2 days" in chunks[1].content

    def test_long_unbroken_text_falls_back_to_character_slicing(self, make_document):
        """Test 5: Long unbroken text eventually falls back to character-level slicing."""
        unbroken = "X" * 350
        doc = make_document(unbroken, file_type="txt")

        chunker = RecursiveChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(doc)

        assert len(chunks) >= 4
        for chunk in chunks:
            assert chunk.char_count <= 100
            assert len(chunk.content.strip()) > 0

    def test_empty_sections_avoid_empty_chunks(self, make_document):
        """Test 6: Empty sections do not produce empty chunks."""
        content = (
            "# Category One\n\n"
            "# Category Two\n\n"
            "Content under Category Two."
        )
        doc = make_document(content, file_type="md")

        chunker = RecursiveChunker(chunk_size=200, overlap=0)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 1
        assert "Content under Category Two." in chunks[0].content
        # Category One was popped/retained in stack appropriately
        assert chunks[0].metadata.get("headings") == ["Category Two"]

    def test_chunk_ordering_sequential_and_deterministic(self, make_document):
        """Test 7: Chunk ordering is sequential, deterministic, and 0-indexed."""
        content = (
            "# Intro\n\nIntro content.\n\n"
            "# Middle\n\nMiddle content.\n\n"
            "# Outro\n\nOutro content."
        )
        doc = make_document(content, file_type="md", metadata={"document_id": "doc-456"})

        chunker = RecursiveChunker(chunk_size=100, overlap=10)
        chunks = chunker.chunk(doc)

        indexes = [c.chunk_index for c in chunks]
        assert indexes == list(range(len(chunks)))
        for c in chunks:
            assert c.chunk_id == f"doc-456:{c.chunk_index}"


# ======================================================================
# Section 15: Property / Invariant Tests
# ======================================================================

class TestChunkingInvariants:
    """Invariant and property tests across both chunkers."""

    @pytest.mark.parametrize("chunker_cls", [FixedSizeChunker, RecursiveChunker])
    def test_universal_chunk_invariants(self, chunker_cls, make_document):
        """Verify universal invariants for all chunks produced."""
        content = (
            "# Header\n\n"
            "Paragraph one with some text.\n\n"
            "Paragraph two with additional detail.\n\n"
            "Paragraph three with concluding notes."
        )
        doc = make_document(content)
        chunker = chunker_cls(chunk_size=80, overlap=15)
        chunks = chunker.chunk(doc)

        assert len(chunks) > 0
        for idx, chunk in enumerate(chunks):
            # Invariant: content is non-empty
            assert len(chunk.content.strip()) > 0
            # Invariant: chunk_index matches list position
            assert chunk.chunk_index == idx
            # Invariant: document_id is present
            assert chunk.document_id
            # Invariant: chunk_id is deterministic and follows format
            assert chunk.chunk_id == f"{chunk.document_id}:{idx}"
            # Invariant: chunk length does not exceed chunk_size
            assert chunk.char_count <= 80
            # Invariant: start_char <= end_char
            if chunk.start_char is not None and chunk.end_char is not None:
                assert chunk.start_char <= chunk.end_char

    def test_chunk_model_immutability(self):
        """Verify that Chunk instances are immutable (frozen)."""
        chunk = Chunk(
            chunk_id="doc:0",
            document_id="doc",
            content="Immutable chunk content",
            chunk_index=0,
        )
        with pytest.raises(ValidationError):
            chunk.content = "Mutated content"

    def test_chunk_model_validation(self):
        """Verify Chunk validation rules."""
        # Empty content rejected
        with pytest.raises(ValidationError):
            Chunk(
                chunk_id="doc:0",
                document_id="doc",
                content="   ",
                chunk_index=0,
            )

        # Invalid start/end char rejected
        with pytest.raises(ValidationError, match="start_char .* cannot be greater than end_char"):
            Chunk(
                chunk_id="doc:0",
                document_id="doc",
                content="Valid content",
                chunk_index=0,
                start_char=50,
                end_char=20,
            )


# ======================================================================
# Section 16: Strategy Comparison Demonstration
# ======================================================================

class TestStrategyComparison:
    """
    Demonstrates and verifies the architectural differences between
    FixedSizeChunker and RecursiveChunker on the same document.
    """

    def test_compare_fixed_vs_recursive_behavior(self, make_document):
        markdown_doc = make_document(
            content=(
                "# Employee Handbook\n\n"
                "## Work Hours\n\n"
                "Standard working hours are 9:00 AM to 5:00 PM Monday through Friday.\n\n"
                "## Vacation Policy\n\n"
                "All full-time employees are eligible for 25 days of paid annual vacation."
            ),
            file_name="handbook.md",
            file_type="md",
        )

        chunk_size = 110
        overlap = 20

        fixed_chunker = FixedSizeChunker(chunk_size=chunk_size, overlap=overlap)
        recursive_chunker = RecursiveChunker(chunk_size=chunk_size, overlap=overlap)

        fixed_chunks = fixed_chunker.chunk(markdown_doc)
        recursive_chunks = recursive_chunker.chunk(markdown_doc)

        # 1. RecursiveChunker extracts and retains section hierarchy
        has_section_meta = any("headings" in c.metadata for c in recursive_chunks)
        assert has_section_meta is True

        # FixedSizeChunker has no awareness of headings
        fixed_has_section = any("headings" in c.metadata for c in fixed_chunks)
        assert fixed_has_section is False

        # 2. In RecursiveChunker, the vacation policy chunk has breadcrumb context
        vacation_chunks = [c for c in recursive_chunks if "Vacation Policy" in c.content]
        assert len(vacation_chunks) >= 1
        assert vacation_chunks[0].metadata.get("section") == "Employee Handbook > Vacation Policy"
        assert vacation_chunks[0].metadata.get("headings") == ["Employee Handbook", "Vacation Policy"]

        # 3. Both strategies respect the configured chunk size limit
        for c in fixed_chunks:
            assert c.char_count <= chunk_size
        for c in recursive_chunks:
            assert c.char_count <= chunk_size
