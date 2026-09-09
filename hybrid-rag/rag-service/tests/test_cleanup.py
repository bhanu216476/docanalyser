from app.ingestion.cleanup import clean_text


def test_clean_text_reduces_multiple_blank_lines():
    input_text = "   Introduction   \n\n\n\n   Retrieval   Augmented   Generation   \n\n\n"
    expected = "Introduction\n\nRetrieval Augmented Generation"
    assert clean_text(input_text) == expected


def test_clean_text_removes_line_leading_and_trailing_whitespace():
    input_text = "  line one  \n  line two  "
    assert clean_text(input_text) == "line one\nline two"


def test_clean_text_normalizes_repeated_spaces_and_tabs():
    input_text = "Word1\t\tWord2    Word3"
    assert clean_text(input_text) == "Word1 Word2 Word3"


def test_clean_text_preserves_paragraph_boundaries():
    input_text = "Paragraph 1 line 1.\nParagraph 1 line 2.\n\nParagraph 2 line 1."
    expected = "Paragraph 1 line 1.\nParagraph 1 line 2.\n\nParagraph 2 line 1."
    assert clean_text(input_text) == expected


def test_clean_text_preserves_unicode_and_punctuation():
    input_text = "  Hello, world! 🚀 — Testing: 100% accurate.  "
    assert clean_text(input_text) == "Hello, world! 🚀 — Testing: 100% accurate."


def test_clean_text_handles_empty_input():
    assert clean_text("") == ""
    assert clean_text("   \n\n   ") == ""
    assert clean_text(None) == ""  # type: ignore
