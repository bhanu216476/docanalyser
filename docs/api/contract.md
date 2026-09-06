# API Contract

This document outlines the initial API contract for the AI/RAG application.

**Note:** This is an initial contract. The actual RAG implementation (retrieval, generation, etc.) will be implemented in future phases.

## Query Request

The request object sent by the client to query the RAG system.

### JSON Structure
```json
{
  "query": "What is the leave policy?"
}
```

### Validation Rules
- `query` (String): 
  - Required (must not be null)
  - Must not be blank/empty
  - Maximum length: 1000 characters

## Query Response

The response object returned by the RAG system containing the generated answer and supporting citations.

### JSON Structure
```json
{
  "answer": "Employees are entitled to...",
  "citations": [
    {
      "document": "employee-handbook.pdf",
      "page": 12
    }
  ]
}
```

## Citation Structure

Structured data representing a single citation used to generate the answer.

### JSON Structure
```json
{
  "document": "employee-handbook.pdf",
  "page": 12
}
```

### Details
- `document` (String): The filename or identifier of the source document.
- `page` (Integer): The page number within the document where the supporting information was found.

## Spring Boot ↔ Python Contract Relationship
The Spring Boot backend and the Python FastAPI service share this exact data contract.
- Spring Boot uses **DTOs (Data Transfer Objects)** (Java 21 `record`s) with Jakarta Bean Validation to ensure the contract at the API boundary.
- Python uses **Pydantic models** to provide runtime type checking and validation for the backend-to-LLM/RAG integration layer.
Both systems produce and consume matching JSON payloads.
