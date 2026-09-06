from pydantic import BaseModel, Field
from typing import List

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="The user query to the RAG system")

class CitationResponse(BaseModel):
    document: str = Field(..., description="The document filename or identifier")
    page: int = Field(..., description="The page number where the citation was found")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated answer")
    citations: List[CitationResponse] = Field(default_factory=list, description="List of citations supporting the answer")
