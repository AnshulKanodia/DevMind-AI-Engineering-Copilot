from typing import List, Optional
from pydantic import BaseModel, Field


class CommitLogItem(BaseModel):
    sha: str = Field(..., description="Commit SHA-1 hash")
    author_name: str
    author_email: str
    date_iso: str
    summary: str
    message: str


class CommitHistoryResponse(BaseModel):
    repo_id: str
    branch: str
    total_returned: int
    commits: List[CommitLogItem]


class FileDiffItem(BaseModel):
    old_path: Optional[str] = None
    new_path: str
    change_type: str = Field(..., description="added, modified, deleted, or renamed")
    additions: int = 0
    deletions: int = 0
    patch_text: str = ""


class BranchDiffResponse(BaseModel):
    repo_id: str
    base_ref: str
    target_ref: str
    total_files_changed: int
    total_additions: int
    total_deletions: int
    files: List[FileDiffItem]


class GitTagItem(BaseModel):
    name: str
    commit_sha: str
    message: Optional[str] = ""


class RepoTagsResponse(BaseModel):
    repo_id: str
    total_tags: int
    tags: List[GitTagItem]
