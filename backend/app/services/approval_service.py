import hashlib
import hmac
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.agents.state import AgentState
from app.schemas.approval import (
    ApprovalActionType,
    ApprovalDecisionRequest,
    ApprovalGateRequest,
    ApprovalGateResponse,
    ApprovalStatus,
)

logger = logging.getLogger("devmind.services.approval")


class HumanInTheLoopApprovalService:
    """Service managing LangGraph conditional interrupts, checkpoint state persistence, and cryptographic approval tokens."""

    def __init__(self):
        self.settings = get_settings()
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._states: Dict[str, AgentState] = {}
        self._lock = threading.Lock()

    def generate_approval_token(self, checkpoint_id: str, reviewed_by: str) -> str:
        """Sign a cryptographic HMAC token proving developer approval."""
        secret = self.settings.SECRET_KEY.encode("utf-8")
        msg = f"{checkpoint_id}:{reviewed_by}:{self.settings.ENCRYPTION_KEY[:8]}".encode("utf-8")
        sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
        return f"devmind-appr-{checkpoint_id[:8]}-{sig[:24]}"

    def verify_approval_token(
        self, checkpoint_id: str, token: str, reviewed_by: Optional[str] = None
    ) -> bool:
        """Verify whether an approval token is cryptographically valid for a checkpoint."""
        if not token or not token.startswith("devmind-appr-"):
            return False

        with self._lock:
            cp = self._checkpoints.get(checkpoint_id)
            if not cp:
                return False
            stored_token = cp.get("approval_token")
            if stored_token and hmac.compare_digest(stored_token, token):
                return True

        # Fallback verification against expected signature if reviewed_by known
        if reviewed_by:
            expected = self.generate_approval_token(checkpoint_id, reviewed_by)
            return hmac.compare_digest(expected, token)

        return False

    def create_checkpoint(
        self,
        state: AgentState,
        request: ApprovalGateRequest,
    ) -> Tuple[ApprovalGateResponse, AgentState]:
        """Pause LangGraph workflow, persist checkpoint state, and issue an approval gate."""
        checkpoint_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=request.expires_in_minutes)

        gate_data = {
            "checkpoint_id": checkpoint_id,
            "repo_id": request.repo_id,
            "status": ApprovalStatus.PENDING,
            "action_type": request.action_type,
            "title": request.title,
            "description": request.description,
            "proposed_patch": request.proposed_patch,
            "target_files": request.target_files,
            "target_branch": request.target_branch,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "comments": None,
            "approval_token": None,
            "can_execute": False,
        }

        # Update AgentState with interrupt details
        updated_state = dict(state)
        updated_state["interrupted"] = True
        updated_state["checkpoint_id"] = checkpoint_id
        updated_state["approval_status"] = ApprovalStatus.PENDING.value
        updated_state["current_step"] = "interrupted_awaiting_approval"
        updated_state["pending_action"] = {
            "action_type": request.action_type.value,
            "title": request.title,
            "target_files": request.target_files,
            "target_branch": request.target_branch,
            "proposed_patch": request.proposed_patch,
        }

        with self._lock:
            self._checkpoints[checkpoint_id] = gate_data
            self._states[checkpoint_id] = updated_state

        logger.info(
            f"Checkpoint {checkpoint_id} created for repo {request.repo_id}: {request.title}"
        )
        return ApprovalGateResponse(**gate_data), updated_state

    def get_checkpoint(self, checkpoint_id: str) -> Optional[ApprovalGateResponse]:
        """Fetch an existing checkpoint by UUID."""
        with self._lock:
            data = self._checkpoints.get(checkpoint_id)
            if not data:
                return None
            return ApprovalGateResponse(**data)

    def list_checkpoints(
        self, repo_id: Optional[str] = None, status: Optional[ApprovalStatus] = None
    ) -> List[ApprovalGateResponse]:
        """List active checkpoints filtered by repo_id or approval status."""
        with self._lock:
            results: List[ApprovalGateResponse] = []
            for cp in self._checkpoints.values():
                if repo_id and cp["repo_id"] != repo_id:
                    continue
                if status and cp["status"] != status:
                    continue
                results.append(ApprovalGateResponse(**cp))
            return sorted(results, key=lambda x: x.created_at, reverse=True)

    def submit_decision(
        self, decision: ApprovalDecisionRequest
    ) -> ApprovalGateResponse:
        """Process developer approval or rejection decision on a checkpoint."""
        now = datetime.now(timezone.utc)
        with self._lock:
            cp = self._checkpoints.get(decision.checkpoint_id)
            if not cp:
                raise ValueError(f"Checkpoint {decision.checkpoint_id} does not exist")

            if cp["status"] != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Checkpoint {decision.checkpoint_id} already resolved with status {cp['status']}"
                )

            # Check expiration
            expires_at = datetime.fromisoformat(cp["expires_at"])
            if now > expires_at:
                cp["status"] = ApprovalStatus.EXPIRED
                raise ValueError(f"Checkpoint {decision.checkpoint_id} has expired")

            cp["status"] = decision.decision
            cp["reviewed_at"] = now.isoformat()
            cp["reviewed_by"] = decision.reviewed_by
            cp["comments"] = decision.comments

            if decision.decision == ApprovalStatus.APPROVED:
                token = self.generate_approval_token(
                    decision.checkpoint_id, decision.reviewed_by
                )
                cp["approval_token"] = token
                cp["can_execute"] = True
            else:
                cp["approval_token"] = None
                cp["can_execute"] = False

            # Update saved AgentState
            saved_state = self._states.get(decision.checkpoint_id)
            if saved_state:
                saved_state["interrupted"] = False
                saved_state["approval_status"] = decision.decision.value
                saved_state["current_step"] = (
                    "approved_resuming" if decision.decision == ApprovalStatus.APPROVED else "rejected_aborted"
                )
                if cp["approval_token"]:
                    if "metadata" not in saved_state or saved_state["metadata"] is None:
                        saved_state["metadata"] = {}
                    saved_state["metadata"]["approval_token"] = cp["approval_token"]

            return ApprovalGateResponse(**cp)

    def resume_state(self, checkpoint_id: str) -> Optional[AgentState]:
        """Retrieve the resumed AgentState following human approval."""
        with self._lock:
            return self._states.get(checkpoint_id)


approval_service = HumanInTheLoopApprovalService()
