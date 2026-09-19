from fastapi import FastAPI
from app.api import health, rag, retrieval

app = FastAPI(
    title="DocAnalyser RAG Service",
    description="Python RAG Service for document processing and retrieval",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(retrieval.router)
app.include_router(rag.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
