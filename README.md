# DocAnalyser

A production-oriented AI/RAG application for intelligent document analysis.

## Project Purpose
DocAnalyser aims to provide a robust, scalable backend for processing documents, embedding them into a vector space, and retrieving relevant context to answer user queries using Large Language Models (LLMs) via the Retrieval-Augmented Generation (RAG) pattern.

## Architecture and Folder Structure
This project utilizes a microservices architecture:
- **React Frontend**: User interface for document upload and querying (Planned).
- **Spring Boot Backend**: API Gateway and core business logic.
- **Python RAG Service**: Handles document ingestion, embeddings, retrieval, and LLM integration.
- **Qdrant**: Vector storage.
- **PostgreSQL**: Relational metadata storage.
- **Redis**: Caching layer.

```
project-root/
├── backend/            # Spring Boot API service
├── rag-service/        # Python RAG pipeline service
├── frontend/           # React user interface (Planned)
├── infrastructure/     # Docker configuration for local development
└── docs/               # Architecture diagrams, ADRs, and coding standards
```

## Required Software
To run this project locally, you must have the following installed:
- **Java**: Version 21
- **Maven**: Installed and available from the terminal
- **Python**: Version 3.12
- **Docker**: Docker Desktop (for running infrastructure dependencies)

## Local Development Setup

### 1. Spring Boot Backend
The Spring Boot backend serves as the main API gateway.

To start the backend:
```bash
cd backend/spring-boot-service
mvn spring-boot:run
```

To verify it is running, check the health endpoint:
```bash
curl http://localhost:8080/api/health
```
You should see:
```json
{"status":"UP"}
```

### 2. Python RAG Service
The Python service handles the AI and vector operations.

Create and activate the virtual environment:
```bash
cd rag-service

# Create the virtual environment using Python 3.12
python -m venv .venv

# Activate the virtual environment (Windows)
.\.venv\Scripts\activate

# Install dependencies (once added)
pip install -r requirements.txt
```

### 3. Infrastructure (Docker)
Start the supporting databases (PostgreSQL, Qdrant, Redis):
```bash
cd infrastructure
docker compose up -d
```
