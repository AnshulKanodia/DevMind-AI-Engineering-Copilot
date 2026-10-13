import pytest
from fastapi.testclient import TestClient

from app.agents.graph import WorkflowGraph
from app.agents.state import create_initial_state
from app.main import app
from app.schemas.approval import (
    ApprovalActionType,
    ApprovalDecisionRequest,
    ApprovalGateRequest,
    ApprovalStatus,
)
from app.services.approval_service import approval_service

client = TestClient(app)


def test_create_checkpoint_and_state_interruption():
    """Verify create_checkpoint registers checkpoint and sets interrupted=True on AgentState."""
    state = create_initial_state(
        repo_id="test-approval-repo",
        user_query="Apply automated security fix to auth.py",
    )
    req = ApprovalGateRequest(
        repo_id="test-approval-repo",
        action_type=ApprovalActionType.DRAFT_PR,
        title="Remediate SQL injection in auth.py",
        description="Replaces raw string query with parameterized query.",
        proposed_patch="--- a/auth.py\n+++ b/auth.py\n-query = f'SELECT ...'\n+cursor.execute(sql, (user_id,))",
        target_files=["backend/app/auth.py"],
        target_branch="devmind/fix-sqli",
    )
    gate_resp, updated_state = approval_service.create_checkpoint(state, req)

    assert gate_resp.checkpoint_id is not None
    assert gate_resp.status == ApprovalStatus.PENDING
    assert gate_resp.can_execute is False
    assert gate_resp.approval_token is None

    # Check updated AgentState
    assert updated_state["interrupted"] is True
    assert updated_state["checkpoint_id"] == gate_resp.checkpoint_id
    assert updated_state["approval_status"] == "pending"
    assert updated_state["current_step"] == "interrupted_awaiting_approval"
    assert updated_state["pending_action"]["target_branch"] == "devmind/fix-sqli"


def test_cryptographic_approval_token_signing_and_verification():
    """Verify HMAC token generation and verification enforce cryptographic integrity."""
    state = create_initial_state(repo_id="crypto-repo", user_query="fix")
    gate_resp, _ = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="crypto-repo",
            title="Update dependencies",
            description="Patch vulnerability",
            proposed_patch="diff",
        ),
    )
    cid = gate_resp.checkpoint_id

    # Decision: Approved
    dec_req = ApprovalDecisionRequest(
        checkpoint_id=cid,
        decision=ApprovalStatus.APPROVED,
        reviewed_by="security-lead@example.com",
        comments="Approved after peer review.",
    )
    dec_resp = approval_service.submit_decision(dec_req)

    assert dec_resp.status == ApprovalStatus.APPROVED
    assert dec_resp.can_execute is True
    assert dec_resp.approval_token is not None
    assert dec_resp.approval_token.startswith("devmind-appr-")

    # Verify token passes verification
    assert approval_service.verify_approval_token(cid, dec_resp.approval_token) is True

    # Forged or corrupted token must fail
    assert approval_service.verify_approval_token(cid, "devmind-appr-fake-token-123") is False
    assert approval_service.verify_approval_token("unknown-checkpoint", dec_resp.approval_token) is False


def test_rejection_decision_prevents_execution():
    """Verify rejecting an approval gate sets can_execute=False and prevents write token issuance."""
    state = create_initial_state(repo_id="reject-repo", user_query="refactor")
    gate_resp, _ = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="reject-repo",
            action_type=ApprovalActionType.GIT_COMMIT,
            title="Refactor core router",
            description="Major architectural changes",
            proposed_patch="diff --git a/router.py",
        ),
    )
    cid = gate_resp.checkpoint_id

    dec_req = ApprovalDecisionRequest(
        checkpoint_id=cid,
        decision=ApprovalStatus.REJECTED,
        reviewed_by="tech-lead@example.com",
        comments="Too risky before upcoming release.",
    )
    dec_resp = approval_service.submit_decision(dec_req)

    assert dec_resp.status == ApprovalStatus.REJECTED
    assert dec_resp.can_execute is False
    assert dec_resp.approval_token is None

    # Resumed state reflects rejection
    resumed = approval_service.resume_state(cid)
    assert resumed["approval_status"] == "rejected"
    assert resumed["current_step"] == "rejected_aborted"


@pytest.mark.asyncio
async def test_langgraph_conditional_interrupt_pauses_workflow():
    """Verify LangGraph WorkflowGraph pauses execution cleanly when interrupted=True."""
    graph = WorkflowGraph()

    async def mocking_node(state):
        state["intent"] = "code_qa"
        return state

    async def interrupt_gate_node(state):
        req = ApprovalGateRequest(
            repo_id=state["repo_id"],
            action_type=ApprovalActionType.DRAFT_PR,
            title="Proposed Patch Gate",
            description="Requires review",
            proposed_patch="diff",
        )
        _, new_state = approval_service.create_checkpoint(state, req)
        return new_state

    async def downstream_mutating_node(state):
        # This node should NEVER execute if interrupted
        state["mutated"] = True
        return state

    graph.add_node("router_node", mocking_node)
    graph.add_node("qa_node", interrupt_gate_node)
    graph.add_node("format_node", downstream_mutating_node)

    initial_state = create_initial_state(repo_id="interrupt-test-repo", user_query="Test pause")
    final_state = await graph.execute(initial_state)

    assert final_state["interrupted"] is True
    assert final_state["checkpoint_id"] is not None
    assert final_state["current_step"] == "interrupted_awaiting_approval"
    assert "mutated" not in final_state  # Proves downstream node was blocked!


def test_approvals_api_endpoints_end_to_end():
    """Verify REST endpoints /api/v1/approvals create, list, inspect, and decide on checkpoints."""
    # 1. Create Checkpoint via POST /checkpoint
    create_payload = {
        "repo_id": "api-demo-repo",
        "action_type": "draft_pr",
        "title": "Fix XSS in UserComment.tsx",
        "description": "Sanitize input with DOMPurify",
        "proposed_patch": "--- a/UserComment.tsx\n+++ b/UserComment.tsx\n-dangerouslySetInnerHTML\n+DOMPurify.sanitize()",
        "target_files": ["frontend/UserComment.tsx"],
        "target_branch": "devmind/fix-xss",
    }
    resp = client.post("/api/v1/approvals/checkpoint", json=create_payload)
    assert resp.status_code == 201
    created_data = resp.json()
    cid = created_data["checkpoint_id"]
    assert created_data["status"] == "pending"
    assert created_data["can_execute"] is False

    # 2. List Checkpoints via GET /
    list_resp = client.get("/api/v1/approvals", params={"repo_id": "api-demo-repo"})
    assert list_resp.status_code == 200
    checkpoints = list_resp.json()
    assert any(c["checkpoint_id"] == cid for c in checkpoints)

    # 3. Get Checkpoint Details via GET /{checkpoint_id}
    detail_resp = client.get(f"/api/v1/approvals/{cid}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Fix XSS in UserComment.tsx"

    # 4. Submit Decision via POST /{checkpoint_id}/decision
    decision_payload = {
        "checkpoint_id": cid,
        "decision": "approved",
        "reviewed_by": "qa-engineer@example.com",
        "comments": "Patch verified against test suite.",
    }
    dec_resp = client.post(f"/api/v1/approvals/{cid}/decision", json=decision_payload)
    assert dec_resp.status_code == 200
    dec_data = dec_resp.json()
    assert dec_data["status"] == "approved"
    assert dec_data["can_execute"] is True
    assert dec_data["approval_token"] is not None

    # 5. Duplicate decision on resolved checkpoint returns 400
    dup_resp = client.post(f"/api/v1/approvals/{cid}/decision", json=decision_payload)
    assert dup_resp.status_code == 400
