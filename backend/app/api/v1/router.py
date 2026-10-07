from fastapi import APIRouter

api_router = APIRouter()

# Sub-routers for auth, repos, agents, etc. will be included here
@api_router.get("/status", tags=["Status"])
async def api_status():
    return {"api_version": "v1", "status": "active"}
