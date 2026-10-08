from typing import Optional
from fastapi import APIRouter, Query, status

from app.schemas.git_metadata import (
    BranchDiffResponse,
    CommitHistoryResponse,
    RepoTagsResponse,
)
from app.services.git_metadata import git_metadata_service

router = APIRouter()


@router.get(
    "/{repo_id}/commits",
    response_model=CommitHistoryResponse,
    summary="Get Commit History",
    description="Retrieves chronological commit log entries with SHA, author, timestamp, and commit message.",
)
async def get_commit_history(
    repo_id: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of commits to retrieve"),
    branch: Optional[str] = Query(None, description="Optional target branch (defaults to HEAD)"),
):
    return await git_metadata_service.get_commit_history(repo_id, limit=limit, branch=branch)


@router.get(
    "/{repo_id}/diff",
    response_model=BranchDiffResponse,
    summary="Get Branch or Commit Diff",
    description="Calculates file modifications, added/deleted line statistics, and unified patch text between two Git refs.",
)
async def get_branch_diff(
    repo_id: str,
    base_ref: str = Query(..., description="Base Git reference (e.g. main, HEAD~1, sha)"),
    target_ref: str = Query(..., description="Target Git reference (e.g. feature-branch, HEAD, sha)"),
):
    return await git_metadata_service.get_branch_diff(repo_id, base_ref=base_ref, target_ref=target_ref)


@router.get(
    "/{repo_id}/tags",
    response_model=RepoTagsResponse,
    summary="Get Git Tags",
    description="Lists all Git release tags with commit hashes and tag annotation messages.",
)
async def get_tags(repo_id: str):
    return await git_metadata_service.get_tags(repo_id)
