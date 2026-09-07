from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint returning service status."""
    return {"status": "UP"}

