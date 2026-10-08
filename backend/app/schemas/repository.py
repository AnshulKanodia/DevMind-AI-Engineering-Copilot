from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class RepoCloneRequest(BaseModel):
    repo_url: str = Field(..., description="Git clone URL (HTTPS or SSH)")
    branch: Optional[str] = Field("main", description="Target git branch to checkout")
    access_token: Optional[str] = Field(None, description="GitHub token for private repository access")
    shallow: bool = Field(True, description="Perform shallow clone with depth=1 to optimize speed and disk")


class RepoFileMetadata(BaseModel):
    file_path: str
    size_bytes: int
    extension: str


class RepoCloneResponse(BaseModel):
    repo_id: str
    repo_url: str
    branch: str
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    sandbox_path: str
    total_files: int
    total_size_bytes: int
    duration_seconds: float
    status: str = "cloned"


class SandboxCleanupResponse(BaseModel):
    repo_id: str
    success: bool
    message: str
