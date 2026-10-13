from typing import List, Optional
from pydantic import BaseModel, Field


class PatchTargetFile(BaseModel):
    """File target and replacement content or diff patch."""

    file_path: str = Field(..., description="Target repository file path")
    patched_content: Optional[str] = Field(
        default=None, description="Full replacement content for the file"
    )
    patch_diff: Optional[str] = Field(
        default=None, description="Unified diff patch hunk for the file"
    )


class ApplyPatchRequest(BaseModel):
    """Request payload to apply an approved patch, create a branch, and open a Draft PR."""

    repo_id: str = Field(..., description="Repository identifier")
    repo_full_name: str = Field(
        default="", description="Target GitHub 'owner/repo' name"
    )
    checkpoint_id: str = Field(
        ..., description="UUID of the Human-in-the-Loop approval checkpoint"
    )
    approval_token: str = Field(
        ..., description="Cryptographically signed HMAC approval token from human developer"
    )
    branch_name: Optional[str] = Field(
        default=None, description="Proposed git branch name e.g. 'devmind/autofix-sqli'"
    )
    base_branch: str = Field(default="main", description="Target base branch for Draft PR")
    commit_message: str = Field(
        default="fix(autofix): apply automated security remediation patch",
        description="Git commit message",
    )
    pr_title: str = Field(
        default="fix(autofix): automated security remediation",
        description="Draft Pull Request title",
    )
    pr_body: str = Field(
        default="Automated remediation patch verified and approved via DevMind Human-in-the-Loop gate.",
        description="Draft Pull Request description body",
    )
    patches: List[PatchTargetFile] = Field(
        default_factory=list, description="List of per-file patch modifications"
    )
    raw_diff: Optional[str] = Field(
        default=None, description="Optional raw unified diff to apply"
    )
    github_token: Optional[str] = Field(
        default=None, description="Optional GitHub OAuth token (raw or Fernet-encrypted)"
    )


class ApplyPatchResponse(BaseModel):
    """Result returned after applying a patch and opening a Draft PR."""

    repo_id: str
    repo_full_name: str
    branch_name: str
    commit_sha: str
    files_modified: List[str] = Field(default_factory=list)
    pr_number: int
    pr_html_url: str
    draft: bool = Field(default=True)
    verified_approval_token: str
    simulated: bool = Field(default=False)
