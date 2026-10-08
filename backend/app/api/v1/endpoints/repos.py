from pathlib import Path
from fastapi import APIRouter, HTTPException, status

from app.schemas.repository import (
    RepoCloneRequest,
    RepoCloneResponse,
    RepoFileMetadata,
    RepoScanResponse,
    SandboxCleanupResponse,
)
from app.services.file_filter import file_filter_service
from app.services.git_cloner import git_cloner_service
from app.services.sandbox_manager import sandbox_manager

router = APIRouter()


@router.post(
    "/clone",
    response_model=RepoCloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Repository to Ephemeral Sandbox",
    description="Clones a remote Git repository into an isolated, temporary sandbox directory with size verification, file filtering, and shallow/sparse checkout.",
)
async def clone_repository(request: RepoCloneRequest):
    result = await git_cloner_service.clone_repository(request)
    return result


@router.get(
    "/{repo_id}/scan",
    response_model=RepoScanResponse,
    summary="Scan Sandboxed Repository",
    description="Applies file filter guards to inventory all eligible source code files and line counts.",
)
async def scan_repository(repo_id: str):
    sandbox_path = sandbox_manager.get_sandbox_path(repo_id)
    if not sandbox_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for repository {repo_id} not found.",
        )

    summary = file_filter_service.scan_repository(sandbox_path)
    file_metadata = [
        RepoFileMetadata(
            relative_path=f.relative_path,
            extension=f.extension,
            size_bytes=f.size_bytes,
            line_count=f.line_count,
        )
        for f in summary.eligible_files
    ]

    return RepoScanResponse(
        repo_id=repo_id,
        total_scanned=summary.total_scanned,
        eligible_count=summary.eligible_count,
        skipped_count=summary.skipped_count,
        total_code_lines=summary.total_code_lines,
        eligible_files=file_metadata,
    )


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
