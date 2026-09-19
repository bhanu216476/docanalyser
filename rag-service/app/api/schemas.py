from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_serializer

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="The user query to the RAG system")

class CitationResponse(BaseModel):
    id: Optional[int] = Field(default=None, ge=1, description="1-based citation identifier matching [N] in answer")
    document: str = Field(..., description="The document filename or identifier")
    page: Optional[int] = Field(default=None, description="The page number where the citation was found")

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if "id" in data and data["id"] is None and "id" not in self.model_fields_set:
            del data["id"]
        if "page" in data and data["page"] is None and "page" not in self.model_fields_set:
            del data["page"]
        return data

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated answer")
    citations: List[CitationResponse] = Field(default_factory=list, description="List of citations supporting the answer")
