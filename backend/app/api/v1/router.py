from fastapi import APIRouter
from app.api.v1.endpoints import auth, git_ops, repos

api_router = APIRouter()

# Register Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Register Repository Ingestion & Sandbox endpoints
api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])

# Register Git Operations & Metadata endpoints
api_router.include_router(git_ops.router, prefix="/git", tags=["Git Metadata"])


@api_router.get("/status", tags=["Status"])
async def api_status():
    return {"api_version": "v1", "status": "active"}
