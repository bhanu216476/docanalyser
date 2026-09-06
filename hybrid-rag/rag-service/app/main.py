from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.query import router as query_router


app = FastAPI(
    title="IntelliResearch RAG Service",
    description="RAG engine for evidence-grounded question answering",
    version="0.1.0"
)


app.include_router(health_router)
app.include_router(query_router)


@app.get("/")
def root():
    return {
        "message": "IntelliResearch RAG Service"
    }