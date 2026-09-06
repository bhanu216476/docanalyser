from fastapi import APIRouter

from app.models.requests import QueryRequest
from app.models.responses import QueryResponse


router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest):
    return QueryResponse(
        answer=f"Received query: {request.query}",
        citations=[]
    )