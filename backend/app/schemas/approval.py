from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Lifecycle state of a Human-in-the-Loop checkpoint gate."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalActionType(str, Enum):
    """Types of sensitive write actions requiring developer approval."""
    GIT_COMMIT = "git_commit"
    DRAFT_PR = "draft_pr"
    APPLY_PATCH = "apply_patch"


class ApprovalGateRequest(BaseModel):
    """Payload to register a new Human-in-the-Loop conditional checkpoint."""

    repo_id: str = Field(..., description="Repository identifier")
    action_type: ApprovalActionType = Field(
        default=ApprovalActionType.DRAFT_PR,
        description="Type of sensitive write operation requested",
    )
    title: str = Field(..., description="Summary title of proposed action")
    description: str = Field(..., description="Detailed rationale for the change")
    proposed_patch: str = Field(..., description="Unified diff or patch code")
    target_files: List[str] = Field(
        default_factory=list, description="Target files affected by the patch"
    )
    target_branch: Optional[str] = Field(
        default=None, description="Proposed branch to push or open PR against"
    )
    requested_by: str = Field(default="devmind-agent", description="Requesting agent name")
    expires_in_minutes: int = Field(default=60, ge=5, le=1440)


class ApprovalDecisionRequest(BaseModel):
    """Payload submitted by authenticated developer to approve or reject an action."""

    checkpoint_id: str = Field(..., description="Unique checkpoint UUID")
    decision: ApprovalStatus = Field(
        ..., description="Developer verdict: 'approved' or 'rejected'"
    )
    reviewed_by: str = Field(..., description="Username or email of the human reviewer")
    comments: Optional[str] = Field(
        default=None, description="Optional review feedback or audit note"
    )


class ApprovalGateResponse(BaseModel):
    """Detailed record of a Human-in-the-Loop checkpoint gate."""

    checkpoint_id: str = Field(..., description="Unique checkpoint UUID")
    repo_id: str
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    action_type: ApprovalActionType
    title: str
    description: str
    proposed_patch: str
    target_files: List[str] = Field(default_factory=list)
    target_branch: Optional[str] = None
    created_at: str
    expires_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    comments: Optional[str] = None
    approval_token: Optional[str] = Field(
        default=None,
        description="Cryptographically signed HMAC token issued upon approval",
    )
    can_execute: bool = Field(
        default=False,
        description="True strictly when valid human approval token has been issued",
    )
