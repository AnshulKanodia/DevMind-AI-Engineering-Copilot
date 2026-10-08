from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user_claims
from app.schemas.repository import (
    RepoCloneRequest,
    RepoCloneResponse,
    SandboxCleanupResponse,
)
from app.services.git_cloner import git_cloner_service
from app.services.sandbox_manager import sandbox_manager

router = APIRouter()


@router.post(
    "/clone",
    response_model=RepoCloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Repository to Ephemeral Sandbox",
    description="Clones a remote Git repository into an isolated, temporary sandbox directory with size verification and shallow checkout.",
)
async def clone_repository(
    request: RepoCloneRequest,
    # Optional authentication guard: in dev or demo mode, claims are accessible
):
    result = await git_cloner_service.clone_repository(request)
    return result


@router.delete(
    "/{repo_id}/sandbox",
    response_model=SandboxCleanupResponse,
    summary="Cleanup Ephemeral Sandbox",
    description="Purges the temporary repository directory from disk to free resources.",
)
async def cleanup_sandbox(repo_id: str):
    success = sandbox_manager.cleanup_sandbox(repo_id)
    return SandboxCleanupResponse(
        repo_id=repo_id,
        success=success,
        message="Sandbox directory purged successfully" if success else "Directory not found",
    )
