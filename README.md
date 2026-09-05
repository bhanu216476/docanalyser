# DocAnalyser

A production-oriented AI/RAG application for intelligent document analysis.

## Architecture Overview

This project utilizes a microservices architecture:
- **React Frontend**: User interface for document upload and querying.
- **Spring Boot Backend**: API Gateway and core business logic.
- **Python RAG Service**: Handles document ingestion, embeddings, retrieval, and LLM integration.
- **Qdrant**: Vector storage.
- **PostgreSQL**: Relational metadata storage.
- **Redis**: Caching layer.

## Technology Stack

- **Frontend**: React (Upcoming)
- **Backend API**: Java / Spring Boot
- **AI/RAG Service**: Python / FastAPI
- **Databases**: PostgreSQL, Qdrant, Redis

## Repository Structure

- `backend/`: Spring Boot API service.
- `rag-service/`: Python RAG pipeline service.
- `frontend/`: React user interface.
- `infrastructure/`: Docker configuration for local development.
- `docs/`: Architecture diagrams, ADRs, and coding standards.

## Local Development

Start the infrastructure components:
```bash
cd infrastructure
docker-compose up -d
```

Run the backend API:
```bash
cd backend/spring-boot-service
./mvnw spring-boot:run
```

Run the RAG service:
```bash
cd rag-service
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Current Project Status

- [x] Project Foundation and Architecture Documentation
- [x] Spring Boot Service Skeleton
- [x] Python RAG Service Skeleton
- [ ] Frontend Integration
- [ ] Document Ingestion Pipeline
- [ ] Retrieval and Reranking Implementation
- [ ] LLM Integration
