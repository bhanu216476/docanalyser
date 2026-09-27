from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api import documents, health, rag, retrieval

app = FastAPI(
    title="DocAnalyser RAG Service",
    description="Python RAG Service for document processing and retrieval",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(retrieval.router)
app.include_router(rag.router)
app.include_router(documents.router)


@app.exception_handler(RequestValidationError)
async def lifecycle_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        serializable_error = dict(error)
        if "ctx" in serializable_error:
            serializable_error["ctx"] = {
                key: str(value) for key, value in serializable_error["ctx"].items()
            }
        errors.append(serializable_error)
    status_code = 422
    if request.url.path == "/api/v1/documents" and any(
        error.get("loc", ())[-1:] == ("document_id",)
        and isinstance(error.get("input"), str)
        and not error["input"].strip()
        for error in errors
    ):
        status_code = 400
    return JSONResponse(status_code=status_code, content={"detail": errors})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
