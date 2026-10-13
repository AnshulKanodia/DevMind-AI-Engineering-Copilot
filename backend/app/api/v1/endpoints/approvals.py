from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.agents.state import create_initial_state
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalGateRequest,
    ApprovalGateResponse,
    ApprovalStatus,
)
from app.services.approval_service import approval_service

router = APIRouter()


@router.post(
    "/checkpoint",
    response_model=ApprovalGateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Human-in-the-Loop conditional checkpoint",
)
async def create_approval_checkpoint(
    request: ApprovalGateRequest,
) -> ApprovalGateResponse:
    """Pause workflow, persist checkpoint state, and register a Human-in-the-Loop approval gate."""
    initial_state = create_initial_state(
        repo_id=request.repo_id,
        user_query=f"Action approval request: {request.title}",
    )
    gate_resp, _ = approval_service.create_checkpoint(initial_state, request)
    return gate_resp


@router.get(
    "",
    response_model=List[ApprovalGateResponse],
    summary="List Human-in-the-Loop checkpoints",
)
async def list_approval_checkpoints(
    repo_id: Optional[str] = Query(None, description="Optional filter by repository ID"),
    status: Optional[ApprovalStatus] = Query(None, description="Optional filter by approval status"),
) -> List[ApprovalGateResponse]:
    """Retrieve all pending, approved, or rejected checkpoints."""
    return approval_service.list_checkpoints(repo_id=repo_id, status=status)


@router.get(
    "/{checkpoint_id}",
    response_model=ApprovalGateResponse,
    summary="Get checkpoint details",
)
async def get_approval_checkpoint(checkpoint_id: str) -> ApprovalGateResponse:
    """Fetch checkpoint gate details and proposed patch diff by ID."""
    checkpoint = approval_service.get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkpoint '{checkpoint_id}' not found",
        )
    return checkpoint


@router.post(
    "/{checkpoint_id}/decision",
    response_model=ApprovalGateResponse,
    summary="Submit human approval or rejection decision",
)
async def submit_approval_decision(
    checkpoint_id: str,
    decision_req: ApprovalDecisionRequest,
) -> ApprovalGateResponse:
    """Process human developer approval or rejection on a checkpoint.
    
    Upon approval, issues a signed cryptographic HMAC token required for write execution.
    """
    if decision_req.checkpoint_id != checkpoint_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkpoint ID mismatch between URL and payload",
        )

    try:
        return approval_service.submit_decision(decision_req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
