from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.context.models import ContextItem, StructuredContext


def test_context_item_defaults_and_structured_count() -> None:
    item = ContextItem(position=1, chunk_id="chunk", content="Evidence", citation="[1] doc")
    context = StructuredContext(items=[item])

    assert item.page_numbers == []
    assert context.item_count == 1


@pytest.mark.parametrize("field", ["position", "page_numbers"])
def test_context_item_rejects_invalid_values(field: str) -> None:
    values = {"position": 0, "page_numbers": [1, 0]}
    with pytest.raises(ValidationError):
        ContextItem(
            position=1 if field != "position" else values[field],
            chunk_id="chunk",
            content="Evidence",
            citation="[1] doc",
            page_numbers=[] if field != "page_numbers" else values[field],
        )


def test_context_item_rejects_blank_evidence() -> None:
    with pytest.raises(ValidationError):
        ContextItem(position=1, chunk_id=" ", content="Evidence", citation="[1] doc")


def test_models_are_frozen() -> None:
    item = ContextItem(position=1, chunk_id="chunk", content="Evidence", citation="[1] doc")
    with pytest.raises(ValidationError):
        item.position = 2  # type: ignore[misc]