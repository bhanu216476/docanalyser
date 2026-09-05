# ADR-001: System Architecture

## Context
We are building a production-oriented AI/RAG application called DocAnalyser. We need to decide on the foundational architecture, databases, and programming languages for the backend services.

## Decision
1. **Spring Boot for Main Backend**: We selected Spring Boot (Java) to serve as the main backend/API Gateway. It provides a robust, typed, and well-structured foundation for business logic, authentication/authorization, and request validation.
2. **Python for RAG/AI Service**: We selected Python (with FastAPI) for the RAG service because the Python ecosystem dominates AI, ML, and NLP libraries (e.g., LlamaIndex, LangChain, PyTorch).
3. **Qdrant as Vector Database**: We selected Qdrant for vector storage and similarity search due to its performance, ease of use, and native support for advanced filtering.
4. **PostgreSQL for Relational Data**: PostgreSQL is chosen for robust, ACID-compliant storage of application state, user data, and document metadata.
5. **Redis for Caching**: Redis will be used for caching and future session management to reduce latency.
6. **Hybrid Retrieval**: We plan to implement a hybrid retrieval architecture (Dense Search + BM25 + Reciprocal Rank Fusion + Reranking) to maximize retrieval accuracy.
7. **Service Separation**: We separated the main backend (Java) from the RAG service (Python) rather than using a single monolith. This allows independent scaling, deployment, and technology choices tailored to the specific domain (business logic vs. AI processing).

## Status
Accepted

## Consequences
- Requires maintaining two separate backend stacks (Java and Python).
- Introduces network latency between the Spring Boot backend and the RAG service.
- Provides a clear boundary of responsibilities and allows specialists (Java developers vs AI engineers) to work in their preferred environments.
