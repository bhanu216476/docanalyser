# DocAnalyser Production Cloud Deployment Guide

This guide covers 1-click cloud deployment to **Render** and **Railway**.

---

## 1. Render Deployment (Recommended - 1 Click Blueprint)

Render natively reads [`render.yaml`](./render.yaml) from this repository to automatically provision:
- **Managed PostgreSQL 15** Database
- **Managed Redis** Cache
- **FastAPI Python RAG Service** (Docker)
- **Spring Boot 3 Backend** (Docker)
- **React Frontend** (Static Site on Global CDN)

### Step-by-Step Instructions:
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your GitHub repository: `bhanu216476/docanalyser`.
4. Render will automatically parse [`render.yaml`](./render.yaml) and list all 5 services and databases.
5. Provide your required environment secrets:
   - `OPENAI_API_KEY`: Your OpenAI API key for embeddings and generation.
   - `QDRANT_URL`: Your Qdrant Cloud Cluster URL (or self-hosted Qdrant URL).
   - `QDRANT_API_KEY`: Your Qdrant API key (if using Qdrant Cloud).
6. Click **Apply**.
7. Render will build and deploy all services simultaneously. Once finished, Render provisions the live services:

### 🚀 Active Render Live URLs:
- **Frontend App:** [https://docanalyser-frontend.onrender.com](https://docanalyser-frontend.onrender.com)
- **Spring Boot API:** [https://docanalyser-backend.onrender.com](https://docanalyser-backend.onrender.com)
- **Backend Health Check:** [https://docanalyser-backend.onrender.com/api/health](https://docanalyser-backend.onrender.com/api/health)
- **Backend Actuator Health:** [https://docanalyser-backend.onrender.com/actuator/health](https://docanalyser-backend.onrender.com/actuator/health)
- **FastAPI RAG Engine:** [https://docanalyser-rag.onrender.com](https://docanalyser-rag.onrender.com)
- **RAG Health Check:** [https://docanalyser-rag.onrender.com/health](https://docanalyser-rag.onrender.com/health)
- **RAG Interactive Swagger Docs:** [https://docanalyser-rag.onrender.com/docs](https://docanalyser-rag.onrender.com/docs)

---

## 2. Railway Deployment

Railway can run the multi-container stack directly from the GitHub repository:

### Step-by-Step Instructions:
1. Log in to [Railway](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select `bhanu216476/docanalyser`.
4. Add **PostgreSQL** and **Redis** database plugins with 1 click from Railway's service menu (+ New -> Database -> PostgreSQL / Redis).
5. Add the 3 application services from the repo:
   - **Backend**: Root Directory: `backend/spring-boot-service` (Uses `backend/spring-boot-service/Dockerfile`)
   - **RAG Service**: Root Directory: `rag-service` (Uses `rag-service/Dockerfile`)
   - **Frontend**: Root Directory: `frontend` (Build command: `npm run build`, Publish directory: `dist`)
6. Link database environment variables:
   - In Backend, set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` from Railway Postgres plugin.
   - In Backend, set `REDIS_HOST`, `REDIS_PORT` from Railway Redis plugin.
   - In Backend, set `RAG_SERVICE_URL` to the private Railway URL of your RAG Service.
   - In Frontend, set `VITE_API_URL` to your Backend public domain.
7. Click **Deploy**.

---

## 3. Vector Database Setup (Qdrant Cloud)

For production cloud deployments, use a free managed Qdrant instance:
1. Create a free account at [Qdrant Cloud Console](https://cloud.qdrant.io/).
2. Create a free cluster (1GB storage).
3. Copy the **Cluster URL** and generate an **API Key**.
4. Set `QDRANT_URL` and `QDRANT_API_KEY` in Render / Railway environment variables.
