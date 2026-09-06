# DTOs and Pydantic Architecture

This document explains the architectural choices for API data modeling in the Spring Boot and Python environments.

## DTOs (Spring Boot)

We use **Data Transfer Objects (DTOs)** in the Spring Boot service to decouple the API endpoints from our internal domain models and entities.

### Key Benefits:
- **API Boundary**: DTOs define a clear, stable contract for clients, independent of internal business logic or database structures.
- **Validation**: By applying Jakarta Bean Validation annotations (e.g., `@NotBlank`, `@Size`), we enforce incoming data constraints immediately at the controller layer.
- **Separation of Concerns**: Prevents accidental exposure of sensitive internal data (like database IDs, passwords, or internal flags) through the REST API.
- **Immutability**: Leveraging Java 21 `record`s ensures that once a request is received, its data cannot be modified, which aligns perfectly with the nature of incoming web requests.

## Pydantic (Python)

We use **Pydantic** in the Python RAG service for robust data validation and settings management.

### Key Benefits:
- **Runtime Validation**: Python is dynamically typed. Pydantic enforces type hints at runtime, ensuring that the data we receive (from Spring Boot or other clients) strictly adheres to our expected schema.
- **Typed Models**: It allows us to define complex nested objects (like `QueryResponse` containing `CitationResponse` lists) with clear, statically analyzable types.
- **FastAPI Integration**: FastAPI natively uses Pydantic for request parsing, validation, and automatic OpenAPI (Swagger) documentation generation.
- **Consistency**: It provides a straightforward way to mirror the Java DTO constraints (like `max_length=1000`) within the Python ecosystem.
