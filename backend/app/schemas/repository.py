from typing import Optional, List
from pydantic import BaseModel, Field


class RepoCloneRequest(BaseModel):
    repo_url: str = Field(..., description="Git clone URL (HTTPS or SSH)")
    branch: Optional[str] = Field("main", description="Target git branch to checkout")
    access_token: Optional[str] = Field(None, description="GitHub token for private repository access")
    shallow: bool = Field(True, description="Perform shallow clone with depth=1 to optimize speed and disk")
    sparse_paths: Optional[List[str]] = Field(
        None, description="Optional subdirectories to check out using git sparse-checkout (e.g., ['src/', 'app/'])"
    )


class RepoFileMetadata(BaseModel):
    relative_path: str
    extension: str
    size_bytes: int
    line_count: int


class RepoCloneResponse(BaseModel):
    repo_id: str
    repo_url: str
    branch: str
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    sandbox_path: str
    total_files_scanned: int
    eligible_files_count: int
    skipped_files_count: int
    total_code_lines: int
    total_size_bytes: int
    duration_seconds: float
    sample_eligible_files: List[str] = []
    status: str = "cloned"


class SandboxCleanupResponse(BaseModel):
    repo_id: str
    success: bool
    message: str


class RepoScanResponse(BaseModel):
    repo_id: str
    total_scanned: int
    eligible_count: int
    skipped_count: int
    total_code_lines: int
    eligible_files: List[RepoFileMetadata]
