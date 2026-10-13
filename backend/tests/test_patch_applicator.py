import pytest
from fastapi.testclient import TestClient

from app.agents.state import create_initial_state
from app.main import app
from app.schemas.approval import (
    ApprovalActionType,
    ApprovalDecisionRequest,
    ApprovalGateRequest,
    ApprovalStatus,
)
from app.schemas.patch import ApplyPatchRequest, PatchTargetFile
from app.services.approval_service import approval_service
from app.services.patch_applicator import patch_applicator_service

client = TestClient(app)


def test_apply_unified_diff_to_string():
    """Verify apply_unified_diff_to_string replaces removed lines with additions cleanly."""
    original = """def fetch_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
"""
    diff_hunk = """@@ -2,2 +2,2 @@
-    query = f"SELECT * FROM users WHERE id = {user_id}"
-    cursor.execute(query)
+    query = "SELECT * FROM users WHERE id = ?"
+    cursor.execute(query, (user_id,))
"""
    patched = patch_applicator_service.apply_unified_diff_to_string(original, diff_hunk)
    assert 'query = "SELECT * FROM users WHERE id = ?"' in patched
    assert "cursor.execute(query, (user_id,))" in patched
    assert "WHERE id = {" not in patched


@pytest.mark.asyncio
async def test_apply_patch_unauthorized_token_raises_permission_error():
    """Verify patch application without valid Human-in-the-Loop approval token is strictly rejected."""
    state = create_initial_state(repo_id="auth-test-repo", user_query="apply patch")
    gate_resp, _ = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="auth-test-repo",
            title="Fix vulnerability",
            description="Remediate SQLi",
            proposed_patch="diff",
        ),
    )
    cid = gate_resp.checkpoint_id

    req = ApplyPatchRequest(
        repo_id="auth-test-repo",
        repo_full_name="octocat/auth-test-repo",
        checkpoint_id=cid,
        approval_token="invalid-or-missing-token",
        patches=[PatchTargetFile(file_path="app/auth.py", patch_diff="diff")],
    )

    with pytest.raises(PermissionError) as exc_info:
        await patch_applicator_service.apply_patch_and_create_draft_pr(req, force_offline=True)

    assert "Zero git commits or PRs are created without a cryptographically verified" in str(exc_info.value)


@pytest.mark.asyncio
async def test_apply_patch_with_verified_approval_token_succeeds():
    """Verify patch application succeeds and creates a Draft PR once approved by human developer."""
    state = create_initial_state(repo_id="patch-repo", user_query="apply patch")
    gate_resp, _ = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="patch-repo",
            action_type=ApprovalActionType.DRAFT_PR,
            title="Fix command injection in utils.py",
            description="Replace os.system with subprocess.run",
            proposed_patch="--- a/utils.py\n+++ b/utils.py\n-os.system(cmd)\n+subprocess.run(cmd)",
            target_files=["backend/app/utils.py"],
            target_branch="devmind/fix-cmdi",
        ),
    )
    cid = gate_resp.checkpoint_id

    # 1. Developer submits Approval decision
    dec_req = ApprovalDecisionRequest(
        checkpoint_id=cid,
        decision=ApprovalStatus.APPROVED,
        reviewed_by="lead-dev@company.com",
        comments="Patch verified; approved for draft PR.",
    )
    dec_resp = approval_service.submit_decision(dec_req)
    valid_token = dec_resp.approval_token
    assert valid_token is not None

    # 2. Trigger patch application with issued token
    apply_req = ApplyPatchRequest(
        repo_id="patch-repo",
        repo_full_name="myorg/patch-repo",
        checkpoint_id=cid,
        approval_token=valid_token,
        branch_name="devmind/fix-cmdi",
        pr_title="fix(security): remediate command injection in utils.py",
        patches=[PatchTargetFile(file_path="backend/app/utils.py", patch_diff="diff")],
    )
    apply_resp = await patch_applicator_service.apply_patch_and_create_draft_pr(
        apply_req, force_offline=True
    )

    assert apply_resp.repo_id == "patch-repo"
    assert apply_resp.branch_name == "devmind/fix-cmdi"
    assert apply_resp.draft is True
    assert apply_resp.verified_approval_token == valid_token
    assert apply_resp.pr_number >= 1
    assert "https://github.com/myorg/patch-repo/pull/" in apply_resp.pr_html_url


def test_apply_autofix_api_endpoint_flow():
    """Verify POST /api/v1/approvals/{checkpoint_id}/apply-autofix endpoint end-to-end."""
    # 1. Create Checkpoint via API
    create_resp = client.post(
        "/api/v1/approvals/checkpoint",
        json={
            "repo_id": "api-patch-repo",
            "action_type": "draft_pr",
            "title": "Fix SQL injection in db.py",
            "description": "Remediate SQL injection",
            "proposed_patch": "--- a/db.py\n+++ b/db.py\n-raw query\n+safe query",
            "target_files": ["db.py"],
        },
    )
    assert create_resp.status_code == 201
    cid = create_resp.json()["checkpoint_id"]

    # 2. Attempt autofix before approval -> Expect 403 Forbidden
    apply_payload = {
        "repo_id": "api-patch-repo",
        "repo_full_name": "org/api-patch-repo",
        "checkpoint_id": cid,
        "approval_token": "fake-token",
        "patches": [{"file_path": "db.py", "patch_diff": "diff"}],
    }
    unauth_resp = client.post(f"/api/v1/approvals/{cid}/apply-autofix", json=apply_payload)
    assert unauth_resp.status_code == 403

    # 3. Approve Checkpoint
    dec_resp = client.post(
        f"/api/v1/approvals/{cid}/decision",
        json={
            "checkpoint_id": cid,
            "decision": "approved",
            "reviewed_by": "sec-ops@company.com",
            "comments": "Approved",
        },
    )
    assert dec_resp.status_code == 200
    issued_token = dec_resp.json()["approval_token"]

    # 4. Attempt autofix with approved token -> Expect 200 OK
    apply_payload["approval_token"] = issued_token
    success_resp = client.post(f"/api/v1/approvals/{cid}/apply-autofix", json=apply_payload)
    assert success_resp.status_code == 200
    res_data = success_resp.json()
    assert res_data["draft"] is True
    assert res_data["verified_approval_token"] == issued_token
    assert res_data["branch_name"].startswith("devmind/autofix-")
