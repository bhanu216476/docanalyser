from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="User's question"
    )

    document_ids: list[str] = Field(
        default_factory=list,
        description="Documents to search"
    )