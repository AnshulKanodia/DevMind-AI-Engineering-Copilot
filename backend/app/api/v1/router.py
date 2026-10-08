from fastapi import APIRouter
from app.api.v1.endpoints import auth, repos

api_router = APIRouter()

# Register Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Register Repository Ingestion & Sandbox endpoints
api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])


@api_router.get("/status", tags=["Status"])
async def api_status():
    return {"api_version": "v1", "status": "active"}
