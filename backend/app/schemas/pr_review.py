from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.github import GitHubInlineReviewComment


class PRReviewSeverity(str, Enum):
    """Severity classification for PR review findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PRReviewIssueCategory(str, Enum):
    """Classification of code issues identified during PR diff review."""
    SECURITY = "security"
    BUG_RISK = "bug_risk"
    BREAKING_CHANGE = "breaking_change"
    MISSING_TESTS = "missing_tests"
    STYLE_STANDARDS = "style_standards"


class PRReviewVerdict(str, Enum):
    """Overall review decision for the pull request."""
    APPROVE = "APPROVE"
    COMMENT = "COMMENT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class PRReviewFinding(BaseModel):
    """Specific line-level issue identified in the pull request diff."""

    file_path: str = Field(..., description="File path relative to repository root")
    line_number: int = Field(..., ge=1, description="Line number where issue originates")
    category: PRReviewIssueCategory = Field(
        ..., description="Classification category e.g. security or bug_risk"
    )
    severity: PRReviewSeverity = Field(
        ..., description="Severity level of the finding"
    )
    title: str = Field(..., description="Concise headline describing the issue")
    description: str = Field(
        ..., description="Technical explanation of the regression or hazard"
    )
    suggested_patch: Optional[str] = Field(
        default=None, description="Suggested code fix or replacement snippet"
    )
    confidence: float = Field(
        default=0.92, ge=0.0, le=1.0, description="Confidence score of finding"
    )


class PRReviewRequest(BaseModel):
    """Request payload for reviewing a pull request diff."""

    repo_id: str = Field(..., description="Repository identifier")
    pr_number: Optional[int] = Field(
        default=None, description="GitHub PR number if reviewing an open PR"
    )
    repo_full_name: Optional[str] = Field(
        default=None, description="Target repository 'owner/repo' on GitHub"
    )
    raw_diff: Optional[str] = Field(
        default=None, description="Direct unified git diff string to review"
    )
    github_token: Optional[str] = Field(
        default=None, description="Optional GitHub OAuth token (raw or Fernet-encrypted)"
    )
    query: Optional[str] = Field(
        default=None, description="Optional developer review instructions"
    )


class PRReviewResponse(BaseModel):
    """Comprehensive automated Pull Request review report."""

    repo_id: str
    pr_number: Optional[int] = None
    verdict: PRReviewVerdict = Field(
        ..., description="Review verdict: APPROVE, COMMENT, or REQUEST_CHANGES"
    )
    summary: str = Field(
        ..., description="Executive Markdown summary of PR review findings"
    )
    findings: List[PRReviewFinding] = Field(
        default_factory=list, description="Structured list of code findings"
    )
    inline_comments: List[GitHubInlineReviewComment] = Field(
        default_factory=list,
        description="Formatted inline review comments ready for GitHub posting",
    )
    files_reviewed: List[str] = Field(
        default_factory=list, description="List of files inspected in the diff"
    )
    total_additions: int = Field(default=0, ge=0)
    total_deletions: int = Field(default=0, ge=0)
    model_used: str = Field(
        default="pr-review-diff-analyzer",
        description="Analyzer engine or LLM model used for review",
    )
