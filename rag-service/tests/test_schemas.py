import pytest
from pydantic import ValidationError
from app.api.schemas import QueryRequest, QueryResponse, CitationResponse

def test_query_request_valid():
    request = QueryRequest(query="What is the leave policy?")
    assert request.query == "What is the leave policy?"

def test_query_request_missing_query():
    with pytest.raises(ValidationError):
        QueryRequest()

def test_query_request_empty_query():
    with pytest.raises(ValidationError) as exc_info:
        QueryRequest(query="")
    assert "String should have at least 1 character" in str(exc_info.value) or "min_length" in str(exc_info.value)

def test_query_request_exceeds_max_length():
    long_query = "a" * 1001
    with pytest.raises(ValidationError) as exc_info:
        QueryRequest(query=long_query)
    assert "String should have at most 1000 characters" in str(exc_info.value) or "max_length" in str(exc_info.value)

def test_citation_response_valid():
    citation = CitationResponse(document="employee-handbook.pdf", page=12)
    assert citation.document == "employee-handbook.pdf"
    assert citation.page == 12

def test_query_response_valid():
    citation = CitationResponse(document="employee-handbook.pdf", page=12)
    response = QueryResponse(answer="Example answer", citations=[citation])
    assert response.answer == "Example answer"
    assert len(response.citations) == 1
    assert response.citations[0].document == "employee-handbook.pdf"
    assert response.citations[0].page == 12

def test_query_response_serialization():
    citation = CitationResponse(document="employee-handbook.pdf", page=12)
    response = QueryResponse(answer="Example answer", citations=[citation])
    json_data = response.model_dump()
    assert json_data == {
        "answer": "Example answer",
        "citations": [
            {
                "document": "employee-handbook.pdf",
                "page": 12
            }
        ]
    }
