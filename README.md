# DocAnalyser - Enterprise RAG Platform

A production-grade, containerized AI/RAG application for intelligent document analysis, hybrid search, citation verification, and factual question-answering.

---

## 1. System Architecture

DocAnalyser employs an enterprise microservices architecture containerized with Docker and unified via Docker Compose:

```text
                    USER / BROWSER
                          │
                          ▼
                React Frontend (Vite)
                     Port: 5173
                          │
                          ▼ (Browser REST/JSON)
                 Spring Boot API
                     Port: 8080
                          │
                          ▼ (Docker Network DNS)
                Python RAG Service
                     Port: 8000
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   Qdrant v1.9.0    PostgreSQL 15        Redis 7
     Port: 6333       Port: 5432        Port: 6379
     (Vectors)        (Metadata)       (Cache/State)
                          ▲
                          │
                 n8n Automation Flow
                     Port: 5678
```

### Services Overview

* **React Frontend (`frontend/`):** React 18 + Vite SPA served via production-grade Nginx. Provides document ingestion, Q&A dashboard with citation cards, claim verification badges, and live confidence score metrics.
* **Spring Boot Backend (`backend/`):** Java 21 Spring Boot 3.3 service managing security (JWT), user authentication, Flyway database migrations, API routing, and Redis caching.
* **Python RAG Service (`rag-service/`):** Python 3.12 FastAPI service executing hybrid dense + BM25 retrieval, Reciprocal Rank Fusion (RRF), citation parsing, and NLI-based claim verification.
* **Qdrant Vector Database (`qdrant`):** Persistent vector storage on ports `6333` / `6334`.
* **PostgreSQL (`postgres`):** Relational database on port `5432` for document metadata and user entities.
* **Redis (`redis`):** In-memory cache on port `6379` for document state and session storage.
* **n8n (`n8n`):** Workflow automation and Google Drive ingestion connectors on port `5678`.

---

## 2. One-Command Startup (Docker Compose)

### Prerequisites
* Docker Engine 24.0+ & Docker Compose v2.20+
* Free ports: `5173`, `8080`, `8000`, `6333`, `5432`, `6379`, `5678`

### Quick Start

1. **Clone the repository and enter the directory:**
   ```bash
   cd "RAG base"
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

3. **Start the complete platform:**
   ```bash
   docker compose up --build
   ```
   *(Or using the infrastructure folder directly: `docker compose -f infrastructure/docker-compose.yml up --build`)*

4. **Start in background (detached mode):**
   ```bash
   docker compose up --build -d
   ```

---

## 3. Platform URLs & Health Endpoints

| Component | URL | Health Check / Status |
| :--- | :--- | :--- |
| **React Frontend** | [http://localhost:5173](http://localhost:5173) | `http://localhost:5173/health` |
| **Spring Boot API** | [http://localhost:8080](http://localhost:8080) | `http://localhost:8080/api/health` |
| **FastAPI RAG Service** | [http://localhost:8000](http://localhost:8000) | `http://localhost:8000/health` |
| **FastAPI Swagger Docs**| [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API Explorer |
| **Qdrant Vector DB** | [http://localhost:6333](http://localhost:6333) | `http://localhost:6333/dashboard` |
| **n8n Workflow Hub** | [http://localhost:5678](http://localhost:5678) | `http://localhost:5678/healthz` |
| **PostgreSQL** | `localhost:5432` | `pg_isready -U postgres -d docanalyser` |
| **Redis** | `localhost:6379` | `redis-cli ping` |

---

## 4. Common Docker Commands

* **Check container health & status:**
  ```bash
  docker compose ps
  ```
* **View all logs:**
  ```bash
  docker compose logs -f
  ```
* **View specific service logs:**
  ```bash
  docker compose logs -f backend
  docker compose logs -f rag-service
  docker compose logs -f frontend
  ```
* **Stop platform without losing persistent data:**
  ```bash
  docker compose down
  ```
* **Rebuild images:**
  ```bash
  docker compose build
  ```

---

## 5. Local Development (Without Docker)

### Spring Boot Backend
```bash
cd backend/spring-boot-service
mvn spring-boot:run
```

### Python RAG Service
```bash
cd rag-service
python -m venv .venv
.\.venv\Scripts\activate       # Windows
source .venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### React Frontend
```bash
cd frontend
npm install
npm run dev
```

For detailed deployment and architecture documentation, see [docs/deployment/docker.md](file:///c:/Users/CH%20BHANU/OneDrive/Desktop/RAG%20base/docs/deployment/docker.md).
