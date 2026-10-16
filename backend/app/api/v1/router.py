from fastapi import APIRouter
from app.api.v1.endpoints import agents, approvals, auth, eval, git_ops, guardrails, repos, scans

api_router = APIRouter()

# Register Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Register Repository Ingestion & Sandbox endpoints
api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])

# Register Git Operations & Metadata endpoints
api_router.include_router(git_ops.router, prefix="/git", tags=["Git Metadata"])

# Register Multi-Agent Orchestration & SSE Streaming endpoints
api_router.include_router(agents.router, prefix="/agents", tags=["Agents & Streaming"])

# Register On-Demand SAST, Bug & Security Scan endpoints
api_router.include_router(scans.router, prefix="/scans", tags=["SAST & Security Scans"])

# Register Human-in-the-Loop Checkpoint & Approval endpoints
api_router.include_router(approvals.router, prefix="/approvals", tags=["Human Approvals"])

# Register Token Guardrails & Usage Accounting endpoints
api_router.include_router(guardrails.router, prefix="/guardrails", tags=["Guardrails & Token Usage"])

# Register RAG Golden Dataset & Evaluation endpoints
api_router.include_router(eval.router, prefix="/eval", tags=["RAG Golden Evaluation"])


@api_router.get("/status", tags=["Status"])
async def api_status():
    return {"api_version": "v1", "status": "active"}
