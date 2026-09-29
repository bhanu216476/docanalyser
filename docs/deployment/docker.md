# DocAnalyser RAG Platform - Complete Docker Deployment Guide

## 1. System Architecture

DocAnalyser is containerized into a multi-service enterprise RAG stack orchestrated via Docker Compose.

```text
                    BROWSER / CLIENT
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
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      Qdrant v1.9.0   PostgreSQL 15     Redis 7
        Port: 6333      Port: 5432     Port: 6379
        (Vectors)      (Metadata)     (Cache/State)
                           ▲
                           │
                  n8n Ingestion Flow
                     Port: 5678
```

### Container Services Summary

| Service | Technology | Internal Port | Host Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **frontend** | React 18 + Vite + Nginx | 5173 | 5173 | Production SPA serving Web UI, Q&A dashboard, and health metrics |
| **backend** | Spring Boot 3.3 (Java 21) | 8080 | 8080 | Authentication, Flyway migrations, API gateway, Redis state caching |
| **rag-service** | FastAPI (Python 3.12) | 8000 | 8000 | Dense + BM25 hybrid retrieval, RRF fusion, citation verification |
| **qdrant** | Qdrant v1.9.0 | 6333, 6334 | 6333, 6334 | Persistent vector storage and cosine similarity search |
| **postgres** | PostgreSQL 15 | 5432 | 5432 | Relational document metadata, user entities, and chat sessions |
| **redis** | Redis 7 | 6379 | 6379 | In-memory cache for document states, sessions, and deduplication |
| **n8n** | n8n v1.60.1 | 5678 | 5678 | Automated document ingestion workflows & Google Drive webhooks |

---

## 2. Prerequisites

* **Docker Engine:** Version 24.0+ or Docker Desktop 4.30+
* **Docker Compose:** Version v2.20+ (supports `include` and service health dependencies)
* **Hardware:** Minimum 4 GB RAM available, 10 GB free disk space
* **OS:** Linux, macOS, or Windows (WSL2 backend)

---

## 3. Environment Configuration

Copy the provided `.env.example` file to create your local `.env`:

```bash
cp .env.example .env
```

Ensure your `.env` contains:

```dotenv
# Primary Environment Profiles
SPRING_PROFILES_ACTIVE=docker
ENVIRONMENT=production

# Database & Cache
POSTGRES_DB=docanalyser
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
REDIS_HOST=redis
REDIS_PORT=6379

# Vector Store
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=documents

# Internal Networking
RAG_SERVICE_URL=http://rag-service:8000
DB_HOST=postgres

# Browser Accessible API Addresses
VITE_API_URL=http://localhost:8080
VITE_RAG_URL=http://localhost:8000

# Security Tokens (Placeholders for local dev; generate random keys in production)
JWT_SECRET=changeme-production-secure-key-docanalyser-min-32-chars
N8N_INGESTION_TOKEN=docanalyser-n8n-internal-token-secret
N8N_ENCRYPTION_KEY=n8n-docanalyser-secret-encryption-key-32chars

# LLM Providers (Optional for mock pipelines; required for live OpenAI inference)
OPENAI_API_KEY=your_openai_api_key_here
```

> [!IMPORTANT]
> Never commit `.env` or paste live secrets into source control. `.env` is explicitly ignored in `.gitignore`.

---

## 4. One-Command Startup

To build and start the complete platform with a single command from the project root:

```bash
docker compose up --build
```

Alternatively, starting via the infrastructure directory:

```bash
docker compose -f infrastructure/docker-compose.yml up --build
```

To run in detached (background) mode:

```bash
docker compose up --build -d
```

---

## 5. Service URLs and Endpoints

Once running, access the services using your browser:

* **React Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
* **Spring Boot API:** [http://localhost:8080](http://localhost:8080)
  * Health Endpoint: [http://localhost:8080/api/health](http://localhost:8080/api/health)
  * Actuator Metrics: [http://localhost:8080/actuator/health](http://localhost:8080/actuator/health)
* **Python RAG Service (FastAPI):** [http://localhost:8000](http://localhost:8000)
  * Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
  * Health Endpoint: [http://localhost:8000/health](http://localhost:8000/health)
* **Qdrant Vector Database:** [http://localhost:6333](http://localhost:6333)
  * Web Dashboard: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
* **n8n Workflow Automation:** [http://localhost:5678](http://localhost:5678)
* **PostgreSQL Database:** `localhost:5432` (database: `docanalyser`, user: `postgres`)
* **Redis Cache:** `localhost:6379`

---

## 6. Service Health Checks & Startup Sequence

Services employ automated Docker health checks to prevent premature connections:

1. **PostgreSQL 15:**
   * Healthcheck: `pg_isready -U postgres -d docanalyser`
   * Frequency: Every 5 seconds, retries 5 times.
2. **Redis 7:**
   * Healthcheck: `redis-cli ping`
   * Frequency: Every 5 seconds.
3. **Qdrant:**
   * Healthcheck: TCP socket readiness on port 6333 (`bash -c ':> /dev/tcp/127.0.0.1/6333'`).
   * Frequency: Every 5 seconds.
4. **Python RAG Service:**
   * Healthcheck: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`
   * Depends on: `qdrant` (condition: `service_healthy`).
5. **Spring Boot Backend:**
   * Healthcheck: `wget --no-verbose --tries=1 --spider http://localhost:8080/api/health`
   * Depends on: `postgres`, `redis`, and `rag-service` (conditions: `service_healthy`).
6. **React Frontend:**
   * Healthcheck: `wget --no-verbose --tries=1 --spider http://localhost:5173/health`
   * Depends on: `backend` (condition: `service_healthy`).

---

## 7. Persistent Named Volumes

All stateful data is preserved in managed Docker named volumes:

* `docanalyser_postgres_data`: Stores PostgreSQL database files, schema migrations, and user data.
* `docanalyser_qdrant_data`: Stores Qdrant vector index segments, payload schemas, and collections.
* `docanalyser_redis_data`: Persists Redis snapshots (`dump.rdb`).
* `docanalyser_n8n_data`: Preserves n8n workflows, nodes, and local configurations.

> [!WARNING]
> Do NOT use `docker compose down -v` during standard maintenance, as the `-v` flag deletes all persistent storage volumes. Use `docker compose down` to stop containers safely while keeping your data intact.

---

## 8. Common Docker Operations

### Check Service Status
```bash
docker compose ps
```

### Tail Live Logs
```bash
# View all container logs
docker compose logs -f

# View a specific service log
docker compose logs -f backend
docker compose logs -f rag-service
docker compose logs -f frontend
```

### Stop the Platform
```bash
docker compose down
```

### Rebuild Images
```bash
docker compose build
```

---

## 9. Failure Handling & Troubleshooting

* **PostgreSQL Connection Failures:** Ensure `docanalyser-postgres` has completed its healthcheck (`docker compose ps`). Inspect logs via `docker compose logs postgres`.
* **RAG Service 502 / Connection Refused:** Spring Boot connects to `http://rag-service:8000`. In case of timeout or missing OpenAI key, mock pipelines continue operating in safe fallback mode.
* **CORS Errors in Browser:** The Spring Boot backend includes cross-origin configuration supporting `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`, `HEAD`, and `PATCH` across all origins in development profiles.
* **Port Conflicts:** If ports 5173, 8080, 8000, 5432, 6379, or 5678 are occupied on your host machine, reassign the corresponding port in your `.env` file (e.g. `FRONTEND_PORT=5174`).
