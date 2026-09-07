# ADR-002: Markdown Loader Strategy (Preserve Markdown Syntax)

## Context
During Day 3 implementation of the ingestion pipeline, we needed to decide how the `MarkdownLoader` handles Markdown files (`.md`, `.markdown`).

Two primary options were evaluated:
- **Option A — Preserve Markdown**: Load and keep raw Markdown syntax intact (`# Heading`, `**bold**`, `- list items`, ````code blocks````).
- **Option B — Convert Markdown to Plain Text**: Strip or transform Markdown formatting into plain unformatted prose using a parser library (e.g. `markdown`, `mistune`, or `beautifulsoup4`).

## Decision
We selected **Option A: Preserve Markdown Syntax**.

## Rationale
1. **Preservation of Structural Hierarchy**: Markdown headers (`#`, `##`, `###`) and structured elements provide explicit semantic cues about section breaks and context. Downstream document chunking stages can use these boundaries to build hierarchical, semantically cohesive chunks.
2. **Lossless Ingestion**: Converting Markdown to plain text is a lossy and irreversible transformation. Ingestion should focus on faithful document capture (`FILE → CLEAN TEXT`) without prematurely discarding structural data.
3. **Minimal Dependencies**: Preserving Markdown syntax requires no external parsing libraries, adhering to our principle of avoiding unnecessary project dependencies. Python's standard library `pathlib` and string methods are fully sufficient.
4. **Separation of Concerns**: Any formatting transformations or plain-text conversions needed for specific embedding models belong in later chunking or embedding transformation steps, not the raw file loader.

## Status
Accepted

## Consequences
- The `Document.content` will contain Markdown syntax tokens.
- Future chunking modules must be designed to accommodate or take advantage of Markdown structure.
- Ingestion dependencies remain minimal with zero added external packages for Markdown loading.
