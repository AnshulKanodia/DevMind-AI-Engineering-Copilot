import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import encrypt_token
from app.schemas.github import (
    GitHubDraftPRCreateRequest,
    GitHubInlineReviewComment,
    GitHubIssueCreateRequest,
    GitHubPRReviewSubmission,
    PRReviewEvent,
)
from app.services.github_client import github_client_service


def test_resolve_oauth_token_plaintext_and_fernet_encrypted():
    """Verify GitHubAPIClient resolves both plaintext tokens and AES-256 Fernet-encrypted tokens."""
    raw_pat = "ghp_1234567890abcdefABCDEF1234567890abcd"
    assert github_client_service.resolve_oauth_token(raw_pat) == raw_pat

    encrypted_pat = encrypt_token(raw_pat)
    assert encrypted_pat.startswith("gAAAAAB")
    assert github_client_service.resolve_oauth_token(encrypted_pat) == raw_pat

    assert github_client_service.resolve_oauth_token(None) is None
    assert github_client_service.resolve_oauth_token("   ") is None


def test_build_headers_includes_github_api_version_and_bearer():
    """Verify GitHub API v2022-11-28 headers and Bearer authorization header."""
    encrypted = encrypt_token("gho_secret_oauth_token_99")
    headers = github_client_service.build_headers(encrypted)

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["Authorization"] == "Bearer gho_secret_oauth_token_99"


@pytest.mark.asyncio
async def test_fetch_pull_request_diff_offline_simulation():
    """Verify fetch_pull_request_diff returns deterministic PR file changes in offline mode."""
    diff = await github_client_service.fetch_pull_request_diff(
        repo_full_name="AnshulKanodia/DevMind-AI-Engineering-Copilot",
        pr_number=42,
        force_offline=True,
    )
    assert diff.repo_full_name == "AnshulKanodia/DevMind-AI-Engineering-Copilot"
    assert diff.pr_number == 42
    assert len(diff.files) == 2
    assert diff.total_additions == 9
    assert diff.total_deletions == 2
    assert "SELECT user_id, role FROM sessions" in diff.raw_diff


@pytest.mark.asyncio
async def test_fetch_pull_request_diff_mocked_github_api():
    """Verify fetch_pull_request_diff parses live GitHub REST API JSON payloads."""
    pr_json = {
        "title": "fix(security): parameterize SQL session lookup",
        "body": "Replaces f-string interpolation with parameterized SQL.",
        "state": "open",
        "user": {"login": "octocat"},
        "base": {"ref": "main"},
        "head": {"ref": "fix/sql-param", "sha": "99887766554433221100aabbccddeeff00112233"},
    }
    files_json = [
        {
            "filename": "backend/app/db.py",
            "status": "modified",
            "additions": 3,
            "deletions": 2,
            "changes": 5,
            "patch": "@@ -10,2 +10,3 @@\n-cursor.execute(f'SELECT * FROM t WHERE id={x}')\n+cursor.execute('SELECT * FROM t WHERE id=?', (x,))",
        }
    ]

    mock_pr_resp = MagicMock(status_code=200)
    mock_pr_resp.json.return_value = pr_json
    mock_files_resp = MagicMock(status_code=200)
    mock_files_resp.json.return_value = files_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_pr_resp, mock_files_resp]
        diff = await github_client_service.fetch_pull_request_diff(
            repo_full_name="octocat/hello-world",
            pr_number=7,
            token="ghp_live_token_test",
        )

    assert diff.title == "fix(security): parameterize SQL session lookup"
    assert diff.author == "octocat"
    assert diff.head_branch == "fix/sql-param"
    assert len(diff.files) == 1
    assert diff.files[0].filename == "backend/app/db.py"
    assert diff.total_additions == 3
    assert diff.total_deletions == 2


@pytest.mark.asyncio
async def test_post_pr_review_mocked_and_offline():
    """Verify post_pr_review sends inline comments to GitHub API and supports offline fallback."""
    submission = GitHubPRReviewSubmission(
        repo_full_name="octocat/hello-world",
        pr_number=12,
        commit_id="abcdef1234567890",
        event=PRReviewEvent.REQUEST_CHANGES,
        body="Detected SQL injection risk in session query.",
        comments=[
            GitHubInlineReviewComment(
                path="backend/app/services/session_auth.py",
                line=17,
                body="Use parameterized SQL placeholders instead of f-string interpolation.",
            )
        ],
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "id": 4455,
        "state": "CHANGES_REQUESTED",
        "html_url": "https://github.com/octocat/hello-world/pull/12#pullrequestreview-4455",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await github_client_service.post_pr_review(
            submission=submission,
            token="ghp_valid_token",
        )

    assert res.review_id == 4455
    assert res.state == "CHANGES_REQUESTED"
    assert res.submitted_comments_count == 1
    assert res.simulated is False

    # Offline fallback verification
    offline_res = await github_client_service.post_pr_review(
        submission=submission,
        force_offline=True,
    )
    assert offline_res.simulated is True
    assert offline_res.submitted_comments_count == 1


@pytest.mark.asyncio
async def test_create_issue_and_draft_pull_request():
    """Verify issue creation, branch creation, and draft PR creation via GitHubAPIClient."""
    issue_req = GitHubIssueCreateRequest(
        repo_full_name="octocat/hello-world",
        title="[Security] CWE-89 SQL Injection in session_auth.py",
        body="Automated DevMind audit identified unparameterized SQL query on line 17.",
        labels=["security", "devmind-ai"],
    )
    issue_res = await github_client_service.create_issue(issue_req, force_offline=True)
    assert issue_res.issue_number == 501
    assert issue_res.simulated is True
    assert "security" in issue_res.labels

    branch_res = await github_client_service.create_branch_ref(
        repo_full_name="octocat/hello-world",
        new_branch="devmind/autofix-pr-12",
        base_sha="a1b2c3d4e5f6",
        force_offline=True,
    )
    assert branch_res["ref"] == "refs/heads/devmind/autofix-pr-12"
    assert branch_res["simulated"] is True

    draft_req = GitHubDraftPRCreateRequest(
        repo_full_name="octocat/hello-world",
        title="fix(security): remediate CWE-89 SQLi in session_auth.py",
        body="Automated patch approved via DevMind Human-in-the-Loop gate.",
        head_branch="devmind/autofix-pr-12",
        base_branch="main",
    )
    draft_res = await github_client_service.create_draft_pull_request(
        draft_req, force_offline=True
    )
    assert draft_res.draft is True
    assert draft_res.simulated is True
    assert draft_res.head_branch == "devmind/autofix-pr-12"
