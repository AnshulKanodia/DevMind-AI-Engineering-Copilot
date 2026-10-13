from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PRReviewEvent(str, Enum):
    """GitHub Pull Request review action types."""
    COMMENT = "COMMENT"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class GitHubPRFileChange(BaseModel):
    """Individual file diff entry from a GitHub Pull Request."""

    filename: str = Field(..., description="Relative file path in repository")
    status: str = Field(
        default="modified",
        description="Change status: 'added', 'modified', 'removed', or 'renamed'",
    )
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    changes: int = Field(default=0, ge=0)
    patch: str = Field(
        default="",
        description="Unified diff patch hunk for this file",
    )


class GitHubPullRequestDiff(BaseModel):
    """Structured representation of a GitHub Pull Request and its changed files."""

    repo_full_name: str = Field(..., description="Full repository name e.g. 'owner/repo'")
    pr_number: int = Field(..., ge=1, description="Pull request number")
    title: str = Field(..., description="Pull request title")
    body: Optional[str] = Field(default="", description="Pull request description body")
    state: str = Field(default="open", description="PR state: 'open' or 'closed'")
    author: str = Field(default="developer", description="GitHub username of PR author")
    base_branch: str = Field(default="main", description="Target base branch")
    head_branch: str = Field(default="feat/update", description="Source head branch")
    head_sha: str = Field(
        default="0000000000000000000000000000000000000000",
        description="Latest commit SHA on head branch",
    )
    files: List[GitHubPRFileChange] = Field(
        default_factory=list, description="List of modified files in the PR"
    )
    raw_diff: str = Field(
        default="", description="Combined unified diff across all changed files"
    )
    total_additions: int = Field(default=0, ge=0)
    total_deletions: int = Field(default=0, ge=0)


class GitHubInlineReviewComment(BaseModel):
    """Line-specific inline review comment attached to a PR diff."""

    path: str = Field(..., description="Relative path of the file being commented on")
    line: int = Field(..., ge=1, description="Line number in the diff (new file side)")
    side: str = Field(default="RIGHT", description="Diff side: 'RIGHT' or 'LEFT'")
    body: str = Field(..., description="Markdown review comment body")


class GitHubPRReviewSubmission(BaseModel):
    """Payload to submit a formal Pull Request review with inline comments."""

    repo_full_name: str = Field(..., description="Target repository 'owner/repo'")
    pr_number: int = Field(..., ge=1)
    commit_id: Optional[str] = Field(
        default=None, description="Optional SHA of the commit being reviewed"
    )
    event: PRReviewEvent = Field(
        default=PRReviewEvent.COMMENT, description="Review verdict action"
    )
    body: str = Field(..., description="Top-level review summary body")
    comments: List[GitHubInlineReviewComment] = Field(
        default_factory=list, description="Inline line-specific comments"
    )


class GitHubPRReviewResult(BaseModel):
    """Response returned after posting a Pull Request review."""

    review_id: int = Field(..., description="GitHub review identifier")
    repo_full_name: str
    pr_number: int
    state: str = Field(..., description="Submitted review state e.g. 'COMMENTED'")
    html_url: str = Field(..., description="Permalink to the GitHub review")
    submitted_comments_count: int = Field(default=0, ge=0)
    simulated: bool = Field(
        default=False,
        description="True if generated in offline simulation mode without live GitHub mutation",
    )


class GitHubIssueCreateRequest(BaseModel):
    """Request payload for creating a GitHub tracking issue."""

    repo_full_name: str = Field(..., description="Target repository 'owner/repo'")
    title: str = Field(..., min_length=3, description="Issue title")
    body: str = Field(..., description="Detailed Markdown issue description")
    labels: List[str] = Field(
        default_factory=lambda: ["devmind-ai", "automated-finding"],
        description="Labels to attach to the issue",
    )
    assignees: List[str] = Field(default_factory=list)


class GitHubIssueResult(BaseModel):
    """Result returned after creating a GitHub tracking issue."""

    issue_number: int = Field(..., ge=1)
    repo_full_name: str
    title: str
    state: str = Field(default="open")
    html_url: str
    labels: List[str] = Field(default_factory=list)
    simulated: bool = Field(default=False)


class GitHubDraftPRCreateRequest(BaseModel):
    """Request payload for creating a Draft Pull Request on GitHub."""

    repo_full_name: str = Field(..., description="Target repository 'owner/repo'")
    title: str = Field(..., min_length=3, description="Draft PR title")
    body: str = Field(..., description="Markdown description detailing automated fixes")
    head_branch: str = Field(..., description="Branch containing proposed changes")
    base_branch: str = Field(default="main", description="Target branch to merge into")
    draft: bool = Field(
        default=True,
        description="Always True by default to enforce safe human review before merge",
    )


class GitHubDraftPRResult(BaseModel):
    """Result returned after opening a Draft Pull Request on GitHub."""

    pr_number: int = Field(..., ge=1)
    repo_full_name: str
    title: str
    head_branch: str
    base_branch: str
    draft: bool = Field(default=True)
    html_url: str
    simulated: bool = Field(default=False)
