"""Heading extraction utilities for document ingestion."""

import re
from bs4 import BeautifulSoup


def extract_headings(text: str, source_type: str = "plain", raw_html: str | None = None) -> list[str]:
    """Extract meaningful headings from document content.

    For HTML sources, HTML heading tags (<h1> through <h6>) are parsed if available.
    For PDF or plain text content, conservative heuristics are applied:
    - Markdown headings (# Heading)
    - Section-numbered headings (1 Introduction, 2.1 Methodology)
    - Short title-cased or uppercase lines without trailing sentence punctuation.

    Duplicate headings are removed while preserving their order of appearance.
    """
    headings: list[str] = []

    # 1. HTML tag extraction if raw_html or HTML content with tags is provided
    html_content = raw_html if raw_html else (text if source_type == "html" and "<" in text and ">" in text else None)
    if html_content:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            for tag in tags:
                clean_h = tag.get_text().strip()
                if clean_h:
                    headings.append(clean_h)
        except Exception:
            pass

    # If HTML tags were found, deduplicate and return
    if headings:
        return _deduplicate(headings)

    # 2. Heuristic extraction for plain text / PDF / fallback HTML
    if not text:
        return []

    lines = text.split("\n")
    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        # Markdown headings: # Heading, ## Heading, etc.
        md_match = re.match(r"^#{1,6}\s+(.+)$", cleaned_line)
        if md_match:
            heading_text = md_match.group(1).strip()
            if heading_text:
                headings.append(heading_text)
            continue

        # Section-numbered headings: e.g., "1 Introduction", "2.1 Methodology", "3. Results"
        num_match = re.match(r"^(\d+(?:\.\d+)*)\s*\.?\s+([A-Z].*)$", cleaned_line)
        if num_match and len(cleaned_line) <= 80:
            # Check if line does not end like a regular sentence with a period/question/exclamation
            if not re.search(r"[.?!]$", cleaned_line):
                headings.append(cleaned_line)
                continue

        # Short title-like lines: 3 <= len <= 60, not ending with sentence punctuation
        if 3 <= len(cleaned_line) <= 60:
            # Exclude lines ending with sentence punctuation (. ? ! , ;)
            if re.search(r"[.?!,;]$", cleaned_line):
                continue
            # Exclude lines starting with lowercase letter (indicating continued sentence)
            if cleaned_line[0].islower():
                continue
            # Check if line is ALL CAPS or Title Case or starts with section number
            words = cleaned_line.split()
            if len(words) <= 8:
                is_all_caps = cleaned_line.isupper() and any(c.isalpha() for c in cleaned_line)
                is_title_case = all(w[0].isupper() or not w[0].isalpha() for w in words if w)
                if is_all_caps or is_title_case:
                    headings.append(cleaned_line)

    return _deduplicate(headings)


def _deduplicate(headings: list[str]) -> list[str]:
    """Preserve order while eliminating duplicate identical strings."""
    seen: set[str] = set()
    result: list[str] = []
    for h in headings:
        if h not in seen:
            seen.add(h)
            result.append(h)
    return result
