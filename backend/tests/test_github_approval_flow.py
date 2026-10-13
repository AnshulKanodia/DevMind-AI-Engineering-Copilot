import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.main import app
from app.schemas.approval import (
    ApprovalActionType,
    ApprovalDecisionRequest,
    ApprovalGateRequest,
    ApprovalStatus,
)
from app.schemas.github import (
    GitHubDraftPRResult,
    GitHubIssueCreateRequest,
    GitHubPRFileChange,
    GitHubPRReviewSubmission,
    GitHubPullRequestDiff,
    PRReviewEvent,
)
from app.schemas.patch import ApplyPatchRequest, PatchTargetFile
from app.schemas.pr_review import PRReviewRequest, PRReviewVerdict
from app.services.approval_service import approval_service
from app.services.github_client import github_client_service
from app.services.patch_applicator import patch_applicator_service
from app.services.pr_review_agent import pr_review_agent_service

client = TestClient(app)

SAMPLE_PR_DIFF = """diff --git a/backend/app/routes/users.py b/backend/app/routes/users.py
--- a/backend/app/routes/users.py
+++ b/backend/app/routes/users.py
@@ -20,6 +20,11 @@ async def get_user_profile(user_id: str):
     return {"user_id": user_id}
 
+async def search_users_by_name(cursor, name_filter: str, default_roles=[]):
+    # Insecure interpolation
+    query = f"SELECT id, username, email FROM users WHERE username LIKE '%{name_filter}%'"
+    cursor.execute(query)
+    return cursor.fetchall()
"""


# ============================================================================
# 1. End-to-End PR Diff Review and Inline Comments Simulation
# ============================================================================


@pytest.mark.asyncio
async def test_pr_diff_review_to_inline_comments_flow():
    """Verify PR diff is analyzed for SQLi and mutable default, producing inline review comments."""
    mock_diff = GitHubPullRequestDiff(
        repo_full_name="acme-corp/user-service",
        pr_number=88,
        title="feat: add user search endpoint",
        body="Adds search_users_by_name helper",
        state="open",
        author="new-developer",
        base_branch="main",
        head_branch="feat/user-search",
        head_sha="11223344556677889900aabbccddeeff11223344",
        files=[
            GitHubPRFileChange(
                filename="backend/app/routes/users.py",
                status="modified",
                additions=6,
                deletions=0,
                changes=6,
                patch="@@ -20,6 +20,11 @@\n+async def search_users_by_name(cursor, name_filter: str, default_roles=[]):\n+    query = f\"SELECT id, username, email FROM users WHERE username LIKE '%{name_filter}%'\"\n+    cursor.execute(query)\n+    return cursor.fetchall()",
            )
        ],
        raw_diff=SAMPLE_PR_DIFF,
        total_additions=6,
        total_deletions=0,
    )

    with patch(
        "app.services.github_client.github_client_service.fetch_pull_request_diff",
        new_callable=AsyncMock,
        return_value=mock_diff,
    ):
        review_req = PRReviewRequest(
            repo_id="acme-corp/user-service",
            pr_number=88,
            repo_full_name="acme-corp/user-service",
        )
        review_res = await pr_review_agent_service.review_pull_request(review_req, force_offline=True)

    assert review_res.verdict == PRReviewVerdict.REQUEST_CHANGES
    assert len(review_res.findings) >= 2
    assert any("SQL Injection" in f.title for f in review_res.findings)
    assert any("Mutable default" in f.title for f in review_res.findings)
    assert len(review_res.inline_comments) == len(review_res.findings)

    # Post Review via GitHub Client
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "id": 9988,
        "state": "CHANGES_REQUESTED",
        "html_url": "https://github.com/acme-corp/user-service/pull/88#pullrequestreview-9988",
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        review_submit_res = await github_client_service.post_pr_review(
            submission=GitHubPRReviewSubmission(
                repo_full_name="acme-corp/user-service",
                pr_number=88,
                commit_id="11223344",
                event=PRReviewEvent.REQUEST_CHANGES,
                body=review_res.summary,
                comments=review_res.inline_comments,
            ),
            token="ghp_test_token",
        )

    assert review_submit_res.review_id == 9988
    assert review_submit_res.state == "CHANGES_REQUESTED"
    assert review_submit_res.simulated is False


# ============================================================================
# 2. Strict Human Approval Gate Enforcement (Zero Write Mutations Without Token)
# ============================================================================


@pytest.mark.asyncio
async def test_zero_mutations_permitted_without_cryptographic_approval_token():
    """Verify that attempting to create a branch or draft PR without an approval token is strictly blocked."""
    state = create_initial_state(
        repo_id="strict-gate-repo", user_query="Apply SQLi remediation"
    )
    gate_resp, _ = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="strict-gate-repo",
            action_type=ApprovalActionType.DRAFT_PR,
            title="Auto-fix SQLi in users.py",
            description="Use parameterized queries",
            proposed_patch="--- a/users.py\n+++ b/users.py\n-raw query\n+safe query",
            target_files=["backend/app/routes/users.py"],
        ),
    )
    cid = gate_resp.checkpoint_id
    assert gate_resp.can_execute is False
    assert gate_resp.approval_token is None

    # 1. Unapproved attempt -> PermissionError
    apply_req = ApplyPatchRequest(
        repo_id="strict-gate-repo",
        repo_full_name="acme/strict-gate-repo",
        checkpoint_id=cid,
        approval_token="unapproved-or-forged-token",
        patches=[PatchTargetFile(file_path="users.py", patch_diff="diff")],
    )
    with pytest.raises(PermissionError) as exc_info:
        await patch_applicator_service.apply_patch_and_create_draft_pr(apply_req, force_offline=True)

    assert "Zero git commits or PRs are created without a cryptographically verified" in str(exc_info.value)

    # 2. Rejection decision -> execution remains strictly blocked
    reject_decision = ApprovalDecisionRequest(
        checkpoint_id=cid,
        decision=ApprovalStatus.REJECTED,
        reviewed_by="security-architect@acme.com",
        comments="Manual refactoring required instead of automated patch.",
    )
    approval_service.submit_decision(reject_decision)
    checkpoint_state = approval_service.get_checkpoint(cid)
    assert checkpoint_state.status == ApprovalStatus.REJECTED
    assert checkpoint_state.can_execute is False
    assert checkpoint_state.approval_token is None


# ============================================================================
# 3. Complete End-to-End Human Approval Gate & Draft PR Creation Lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_full_human_in_the_loop_approval_and_draft_pr_lifecycle():
    """Verify the full lifecycle: checkpoint -> human approval -> HMAC token -> draft PR creation."""
    # 1. Agent registers checkpoint gate
    state = create_initial_state(repo_id="lifecycle-repo", user_query="Remediate SQLi")
    gate_resp, updated_state = approval_service.create_checkpoint(
        state,
        ApprovalGateRequest(
            repo_id="lifecycle-repo",
            action_type=ApprovalActionType.DRAFT_PR,
            title="Parameterize search_users_by_name SQL query",
            description="Fixes CWE-89 by binding name_filter as parameter tuple.",
            proposed_patch="--- a/users.py\n+++ b/users.py\n-query = f'SELECT...'\n+cursor.execute(sql, (f'%{name}%',))",
            target_files=["backend/app/routes/users.py"],
            target_branch="devmind/fix-sqli-users",
        ),
    )
    cid = gate_resp.checkpoint_id
    assert updated_state["interrupted"] is True
    assert updated_state["current_step"] == "interrupted_awaiting_approval"

    # 2. Human developer reviews and approves via API
    dec_resp = client.post(
        f"/api/v1/approvals/{cid}/decision",
        json={
            "checkpoint_id": cid,
            "decision": "approved",
            "reviewed_by": "lead-reviewer@company.com",
            "comments": "Patch reviewed and approved for draft PR submission.",
        },
    )
    assert dec_resp.status_code == 200
    approval_data = dec_resp.json()
    assert approval_data["status"] == "approved"
    assert approval_data["can_execute"] is True
    hmac_token = approval_data["approval_token"]
    assert hmac_token is not None
    assert hmac_token.startswith("devmind-appr-")

    # 3. Apply patch and create Draft PR via REST API
    mock_draft_result = GitHubDraftPRResult(
        pr_number=102,
        repo_full_name="acme/lifecycle-repo",
        title="fix(autofix): parameterize search_users_by_name SQL query",
        head_branch="devmind/fix-sqli-users",
        base_branch="main",
        draft=True,
        html_url="https://github.com/acme/lifecycle-repo/pull/102",
        simulated=False,
    )

    with patch(
        "app.services.github_client.github_client_service.create_draft_pull_request",
        new_callable=AsyncMock,
        return_value=mock_draft_result,
    ), patch(
        "app.services.github_client.github_client_service.create_branch_ref",
        new_callable=AsyncMock,
        return_value={"ref": "refs/heads/devmind/fix-sqli-users", "sha": "123", "simulated": False},
    ):
        apply_resp = client.post(
            f"/api/v1/approvals/{cid}/apply-autofix",
            json={
                "repo_id": "lifecycle-repo",
                "repo_full_name": "acme/lifecycle-repo",
                "checkpoint_id": cid,
                "approval_token": hmac_token,
                "branch_name": "devmind/fix-sqli-users",
                "pr_title": "fix(autofix): parameterize search_users_by_name SQL query",
                "patches": [
                    {"file_path": "backend/app/routes/users.py", "patch_diff": "diff"}
                ],
            },
        )

    assert apply_resp.status_code == 200
    res_body = apply_resp.json()
    assert res_body["pr_number"] == 102
    assert res_body["draft"] is True
    assert res_body["branch_name"] == "devmind/fix-sqli-users"
    assert res_body["verified_approval_token"] == hmac_token
    assert res_body["pr_html_url"] == "https://github.com/acme/lifecycle-repo/pull/102"
