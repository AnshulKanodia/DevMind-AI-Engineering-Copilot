import pytest
from unittest.mock import AsyncMock, patch

from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.github import GitHubPRFileChange, GitHubPullRequestDiff
from app.schemas.pr_review import (
    PRReviewIssueCategory,
    PRReviewRequest,
    PRReviewSeverity,
    PRReviewVerdict,
)
from app.services.pr_review_agent import pr_review_agent_service


SAMPLE_VULNERABLE_DIFF = """diff --git a/backend/app/auth.py b/backend/app/auth.py
--- a/backend/app/auth.py
+++ b/backend/app/auth.py
@@ -10,6 +10,14 @@ def get_user(db, user_id):
     return db.query(user_id)
 
+def authenticate_user(cursor, username: str, password: str, audit_logs=[]):
+    # Insecure query
+    query = f"SELECT * FROM users WHERE username = '{username}'"
+    cursor.execute(query)
+    os.system(f"echo Auth event for {username}")
+    try:
+        pass
+    except:
+        return None
"""

SAMPLE_CLEAN_DIFF_WITH_TEST = """diff --git a/backend/app/calculator.py b/backend/app/calculator.py
--- a/backend/app/calculator.py
+++ b/backend/app/calculator.py
@@ -1,3 +1,6 @@
+def add_numbers(a: int, b: int) -> int:
+    return a + b
diff --git a/backend/tests/test_calculator.py b/backend/tests/test_calculator.py
--- a/backend/tests/test_calculator.py
+++ b/backend/tests/test_calculator.py
@@ -1,3 +1,6 @@
+def test_add_numbers():
+    assert add_numbers(2, 3) == 5
"""


def test_parse_raw_diff():
    """Verify parse_raw_diff extracts files and added line numbers correctly."""
    files = pr_review_agent_service.parse_raw_diff(SAMPLE_VULNERABLE_DIFF)
    assert len(files) == 1
    fname, lines = files[0]
    assert fname == "backend/app/auth.py"
    assert len(lines) >= 8
    # Verify line numbering starts around line 13
    assert lines[0][0] >= 12
    assert "def authenticate_user" in lines[0][1]


def test_analyze_diff_hunks_detects_security_and_bug_risks():
    """Verify analyze_diff_hunks identifies SQL injection, command injection, mutable defaults, and bare except."""
    files = pr_review_agent_service.parse_raw_diff(SAMPLE_VULNERABLE_DIFF)
    findings = pr_review_agent_service.analyze_diff_hunks(files)

    assert len(findings) >= 4
    categories = {f.category for f in findings}
    assert PRReviewIssueCategory.SECURITY in categories
    assert PRReviewIssueCategory.BUG_RISK in categories

    titles = [f.title for f in findings]
    assert any("SQL Injection" in t for t in titles)
    assert any("Command Injection" in t for t in titles)
    assert any("Mutable default" in t for t in titles)
    assert any("Bare except" in t for t in titles)

    # Check suggested patches are provided
    for f in findings:
        assert f.suggested_patch is not None
        assert len(f.suggested_patch) > 5


def test_verdict_computation():
    """Verify compute_verdict assigns REQUEST_CHANGES on vulnerabilities and APPROVE on clean diffs."""
    vuln_files = pr_review_agent_service.parse_raw_diff(SAMPLE_VULNERABLE_DIFF)
    vuln_findings = pr_review_agent_service.analyze_diff_hunks(vuln_files)
    assert pr_review_agent_service.compute_verdict(vuln_findings) == PRReviewVerdict.REQUEST_CHANGES

    clean_files = pr_review_agent_service.parse_raw_diff(SAMPLE_CLEAN_DIFF_WITH_TEST)
    clean_findings = pr_review_agent_service.analyze_diff_hunks(clean_files)
    assert len(clean_findings) == 0
    assert pr_review_agent_service.compute_verdict(clean_findings) == PRReviewVerdict.APPROVE


def test_generate_inline_comments():
    """Verify inline comments contain Markdown badges and suggestion code blocks."""
    vuln_files = pr_review_agent_service.parse_raw_diff(SAMPLE_VULNERABLE_DIFF)
    findings = pr_review_agent_service.analyze_diff_hunks(vuln_files)
    comments = pr_review_agent_service.generate_inline_comments(findings)

    assert len(comments) == len(findings)
    for c in comments:
        assert c.path == "backend/app/auth.py"
        assert c.line >= 12
        assert "```suggestion" in c.body


@pytest.mark.asyncio
async def test_review_pull_request_with_raw_diff():
    """Verify review_pull_request parses diff and renders formatted summary report."""
    req = PRReviewRequest(
        repo_id="test-review-repo",
        raw_diff=SAMPLE_VULNERABLE_DIFF,
    )
    res = await pr_review_agent_service.review_pull_request(req, force_offline=True)

    assert res.repo_id == "test-review-repo"
    assert res.verdict == PRReviewVerdict.REQUEST_CHANGES
    assert len(res.findings) >= 4
    assert len(res.inline_comments) == len(res.findings)
    assert "### DevMind Pull Request Review" in res.summary
    assert "CHANGES REQUESTED" in res.summary
    assert "backend/app/auth.py" in res.files_reviewed


@pytest.mark.asyncio
async def test_review_pull_request_via_github_api_mock():
    """Verify review_pull_request fetches PR diff using GitHubAPIClient when pr_number is specified."""
    mock_diff = GitHubPullRequestDiff(
        repo_full_name="octocat/hello-world",
        pr_number=55,
        title="feat: update greeting",
        body="Updates greeting logic",
        state="open",
        author="octocat",
        base_branch="main",
        head_branch="patch-1",
        head_sha="1234567890abcdef",
        files=[
            GitHubPRFileChange(
                filename="backend/greet.py",
                status="modified",
                additions=1,
                deletions=1,
                changes=2,
                patch="@@ -1,2 +1,2 @@\n-print('hello')\n+print('welcome')",
            )
        ],
        raw_diff="diff --git a/backend/greet.py b/backend/greet.py\n@@ -1,2 +1,2 @@\n-print('hello')\n+print('welcome')",
        total_additions=1,
        total_deletions=1,
    )

    with patch(
        "app.services.github_client.github_client_service.fetch_pull_request_diff",
        new_callable=AsyncMock,
        return_value=mock_diff,
    ):
        req = PRReviewRequest(
            repo_id="octocat/hello-world",
            pr_number=55,
            repo_full_name="octocat/hello-world",
        )
        res = await pr_review_agent_service.review_pull_request(req, force_offline=True)

    assert res.pr_number == 55
    assert res.verdict == PRReviewVerdict.APPROVE
    assert "backend/greet.py" in res.files_reviewed


@pytest.mark.asyncio
async def test_workflow_graph_pr_node_execution():
    """Verify LangGraph multi-agent orchestrator routes PR review query to pr_node."""
    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id="test-pr-repo",
        user_query="Review PR #42 for security regressions and code smells",
    )
    initial_state["metadata"] = {"raw_diff": SAMPLE_VULNERABLE_DIFF}

    final_state = await graph.execute(initial_state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "pr_review"
    assert "### DevMind Pull Request Review" in final_state["final_response"]
    assert "CHANGES REQUESTED" in final_state["final_response"]
    assert final_state["metadata"]["pr_verdict"] == "REQUEST_CHANGES"
    assert final_state["metadata"]["pr_findings_count"] >= 4
