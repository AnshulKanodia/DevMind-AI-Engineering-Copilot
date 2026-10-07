from fastapi import APIRouter
from app.api.v1.endpoints import auth

api_router = APIRouter()

# Register Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@api_router.get("/status", tags=["Status"])
async def api_status():
    return {"api_version": "v1", "status": "active"}
