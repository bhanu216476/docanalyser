from app.ingestion.headings import extract_headings


def test_extract_markdown_style_headings():
    text = "# Introduction\nSome content here.\n## Methodology\nMore text.\n### Results"
    headings = extract_headings(text)
    assert headings == ["Introduction", "Methodology", "Results"]


def test_extract_numbered_headings():
    text = "1 Introduction\nText...\n2 Methodology\nText...\n3 Results"
    headings = extract_headings(text)
    assert "1 Introduction" in headings
    assert "2 Methodology" in headings
    assert "3 Results" in headings


def test_normal_sentences_are_not_detected_as_headings():
    text = "This is a normal sentence explaining the methodology.\nIt contains multiple words and ends with punctuation."
    headings = extract_headings(text)
    assert headings == []


def test_empty_input_returns_empty_list():
    assert extract_headings("") == []
    assert extract_headings("   \n   ") == []


def test_extract_html_headings():
    html = "<html><body><h1>Main Heading</h1><p>Text</p><h2>Section One</h2><h2>Section One</h2></body></html>"
    headings = extract_headings(text=html, source_type="html")
    assert headings == ["Main Heading", "Section One"]
