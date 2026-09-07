from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    page: int | None = None
    content: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)