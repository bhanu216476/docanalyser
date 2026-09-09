"""Document processing pipeline for ingestion."""

from langchain_core.documents import Document

from app.ingestion.cleanup import clean_text
from app.ingestion.headings import extract_headings


def process_documents(documents: list[Document], source_type: str) -> list[Document]:
    """Process a list of LangChain Document objects by applying text cleanup,

    metadata normalization, page tracking (for PDFs), and heading extraction.

    Args:
        documents: List of raw LangChain Document objects.
        source_type: Ingestion source type ("pdf" or "html").

    Returns:
        A list of processed Document objects.
    """
    processed: list[Document] = []

    for idx, doc in enumerate(documents):
        cleaned_content = clean_text(doc.page_content)
        new_metadata = dict(doc.metadata)

        # Normalize source_type
        new_metadata["source_type"] = source_type

        # Page tracking metadata normalization
        if source_type == "pdf":
            if "page" in new_metadata and isinstance(new_metadata["page"], int):
                new_metadata["page_number"] = new_metadata["page"] + 1
            elif "page_number" not in new_metadata:
                new_metadata["page_number"] = idx + 1
        elif source_type == "html":
            # Ensure page_number is not present for HTML sources
            new_metadata.pop("page_number", None)

        # Heading extraction
        headings = extract_headings(cleaned_content, source_type=source_type)
        new_metadata["headings"] = headings

        processed.append(
            Document(
                page_content=cleaned_content,
                metadata=new_metadata
            )
        )

    return processed
