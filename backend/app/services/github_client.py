import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.security import decrypt_token
from app.schemas.github import (
    GitHubDraftPRCreateRequest,
    GitHubDraftPRResult,
    GitHubIssueCreateRequest,
    GitHubIssueResult,
    GitHubPRFileChange,
    GitHubPRReviewResult,
    GitHubPRReviewSubmission,
    GitHubPullRequestDiff,
)

logger = logging.getLogger("devmind.services.github_client")

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


class GitHubAPIClient:
    """GitHub REST API v3 client supporting scoped OAuth tokens, PR diff inspection, inline reviews, issues, and draft PRs."""

    def resolve_oauth_token(self, token_or_encrypted: Optional[str]) -> Optional[str]:
        """Resolve a raw or Fernet-encrypted GitHub OAuth token into plaintext."""
        if not token_or_encrypted:
            return None
        cleaned = token_or_encrypted.strip()
        if not cleaned:
            return None
        # Fernet tokens begin with 'gAAAAAB'
        if cleaned.startswith("gAAAAAB"):
            try:
                return decrypt_token(cleaned)
            except Exception as exc:
                logger.warning(f"Failed to decrypt Fernet GitHub token: {exc}")
                return None
        return cleaned

    def build_headers(self, token_or_encrypted: Optional[str] = None) -> Dict[str, str]:
        """Construct GitHub REST API v2022-11-28 request headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "DevMind-AI-Engineering-Copilot/1.0",
        }
        resolved_token = self.resolve_oauth_token(token_or_encrypted)
        if resolved_token:
            headers["Authorization"] = f"Bearer {resolved_token}"
        return headers

    def _build_simulated_pr_diff(
        self, repo_full_name: str, pr_number: int
    ) -> GitHubPullRequestDiff:
        """Construct a deterministic synthetic Pull Request diff when offline or unauthenticated."""
        sample_patch_1 = (
            "@@ -14,7 +14,10 @@ def verify_user_session(cursor, session_id: str, cache={}):\n"
            "-    cursor.execute('SELECT user_id FROM sessions WHERE id = ?', (session_id,))\n"
            "+    # Fast lookup query\n"
            "+    query = f\"SELECT user_id, role FROM sessions WHERE id = '{session_id}'\"\n"
            "+    cursor.execute(query)\n"
            "     row = cursor.fetchone()\n"
            "+    if row == None:\n"
            "+        return None\n"
            "     return row"
        )
        sample_patch_2 = (
            "@@ -1,5 +1,9 @@\n"
            " export function formatCurrency(amount: number): string {\n"
            "-    return `$${amount.toFixed(2)}`;\n"
            "+    if (amount < 0) {\n"
            "+        return `-$${Math.abs(amount).toFixed(2)}`;\n"
            "+    }\n"
            "+    return `$${amount.toFixed(2)}`;\n"
            " }"
        )
        files = [
            GitHubPRFileChange(
                filename="backend/app/services/session_auth.py",
                status="modified",
                additions=5,
                deletions=1,
                changes=6,
                patch=sample_patch_1,
            ),
            GitHubPRFileChange(
                filename="frontend/src/utils/currency.ts",
                status="modified",
                additions=4,
                deletions=1,
                changes=5,
                patch=sample_patch_2,
            ),
        ]
        raw_diff = (
            f"diff --git a/{files[0].filename} b/{files[0].filename}\n{sample_patch_1}\n\n"
            f"diff --git a/{files[1].filename} b/{files[1].filename}\n{sample_patch_2}"
        )
        return GitHubPullRequestDiff(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            title=f"feat(auth): optimize session lookup and negative currency formatting (#{pr_number})",
            body="Refactors session verification query and adds negative currency formatting support.",
            state="open",
            author="devmind-contributor",
            base_branch="main",
            head_branch=f"feat/pr-{pr_number}-session-auth",
            head_sha="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
            files=files,
            raw_diff=raw_diff,
            total_additions=9,
            total_deletions=2,
        )

    async def fetch_pull_request_diff(
        self,
        repo_full_name: str,
        pr_number: int,
        token: Optional[str] = None,
        force_offline: bool = False,
    ) -> GitHubPullRequestDiff:
        """Fetch PR metadata and per-file unified diff patches from GitHub API."""
        resolved_token = self.resolve_oauth_token(token)
        if force_offline or not resolved_token:
            return self._build_simulated_pr_diff(repo_full_name, pr_number)

        headers = self.build_headers(resolved_token)
        pr_url = f"{GITHUB_API_BASE_URL}/repos/{repo_full_name}/pulls/{pr_number}"
        files_url = f"{GITHUB_API_BASE_URL}/repos/{repo_full_name}/pulls/{pr_number}/files"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                pr_resp = await client.get(pr_url, headers=headers)
                files_resp = await client.get(files_url, headers=headers)

            if pr_resp.status_code == 200 and files_resp.status_code == 200:
                pr_data = pr_resp.json()
                files_data = files_resp.json()

                parsed_files: List[GitHubPRFileChange] = []
                diff_chunks: List[str] = []
                total_add = 0
                total_del = 0

                for f in files_data:
                    patch_str = f.get("patch", "")
                    fname = f.get("filename", "unknown")
                    adds = int(f.get("additions", 0))
                    dels = int(f.get("deletions", 0))
                    total_add += adds
                    total_del += dels
                    parsed_files.append(
                        GitHubPRFileChange(
                            filename=fname,
                            status=f.get("status", "modified"),
                            additions=adds,
                            deletions=dels,
                            changes=int(f.get("changes", adds + dels)),
                            patch=patch_str,
                        )
                    )
                    if patch_str:
                        diff_chunks.append(f"diff --git a/{fname} b/{fname}\n{patch_str}")

                return GitHubPullRequestDiff(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    title=pr_data.get("title", f"PR #{pr_number}"),
                    body=pr_data.get("body") or "",
                    state=pr_data.get("state", "open"),
                    author=(pr_data.get("user") or {}).get("login", "unknown"),
                    base_branch=(pr_data.get("base") or {}).get("ref", "main"),
                    head_branch=(pr_data.get("head") or {}).get("ref", "feature"),
                    head_sha=(pr_data.get("head") or {}).get("sha", ""),
                    files=parsed_files,
                    raw_diff="\n\n".join(diff_chunks),
                    total_additions=total_add,
                    total_deletions=total_del,
                )
        except Exception as exc:
            logger.warning(f"GitHub PR fetch failed for {repo_full_name}#{pr_number}: {exc}")

        return self._build_simulated_pr_diff(repo_full_name, pr_number)

    async def post_pr_review(
        self,
        submission: GitHubPRReviewSubmission,
        token: Optional[str] = None,
        force_offline: bool = False,
    ) -> GitHubPRReviewResult:
        """Post a Pull Request review with inline line-level comments to GitHub."""
        resolved_token = self.resolve_oauth_token(token)
        if not force_offline and resolved_token:
            headers = self.build_headers(resolved_token)
            url = f"{GITHUB_API_BASE_URL}/repos/{submission.repo_full_name}/pulls/{submission.pr_number}/reviews"
            payload: Dict[str, Any] = {
                "event": submission.event.value,
                "body": submission.body,
                "comments": [
                    {
                        "path": c.path,
                        "line": c.line,
                        "side": c.side,
                        "body": c.body,
                    }
                    for c in submission.comments
                ],
            }
            if submission.commit_id:
                payload["commit_id"] = submission.commit_id

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return GitHubPRReviewResult(
                        review_id=int(data.get("id", 1001)),
                        repo_full_name=submission.repo_full_name,
                        pr_number=submission.pr_number,
                        state=data.get("state", "COMMENTED"),
                        html_url=data.get(
                            "html_url",
                            f"https://github.com/{submission.repo_full_name}/pull/{submission.pr_number}#pullrequestreview-1001",
                        ),
                        submitted_comments_count=len(submission.comments),
                        simulated=False,
                    )
            except Exception as exc:
                logger.warning(f"GitHub PR review submission failed: {exc}")

        return GitHubPRReviewResult(
            review_id=9000 + submission.pr_number,
            repo_full_name=submission.repo_full_name,
            pr_number=submission.pr_number,
            state=f"{submission.event.value}ED" if submission.event.value == "COMMENT" else submission.event.value,
            html_url=f"https://github.com/{submission.repo_full_name}/pull/{submission.pr_number}#pullrequestreview-{9000 + submission.pr_number}",
            submitted_comments_count=len(submission.comments),
            simulated=True,
        )

    async def create_issue(
        self,
        request: GitHubIssueCreateRequest,
        token: Optional[str] = None,
        force_offline: bool = False,
    ) -> GitHubIssueResult:
        """Create a GitHub tracking issue for security findings or architectural regressions."""
        resolved_token = self.resolve_oauth_token(token)
        if not force_offline and resolved_token:
            headers = self.build_headers(resolved_token)
            url = f"{GITHUB_API_BASE_URL}/repos/{request.repo_full_name}/issues"
            payload: Dict[str, Any] = {
                "title": request.title,
                "body": request.body,
                "labels": request.labels,
            }
            if request.assignees:
                payload["assignees"] = request.assignees

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 201:
                    data = resp.json()
                    return GitHubIssueResult(
                        issue_number=int(data.get("number", 1)),
                        repo_full_name=request.repo_full_name,
                        title=data.get("title", request.title),
                        state=data.get("state", "open"),
                        html_url=data.get(
                            "html_url",
                            f"https://github.com/{request.repo_full_name}/issues/1",
                        ),
                        labels=request.labels,
                        simulated=False,
                    )
            except Exception as exc:
                logger.warning(f"GitHub issue creation failed: {exc}")

        return GitHubIssueResult(
            issue_number=501,
            repo_full_name=request.repo_full_name,
            title=request.title,
            state="open",
            html_url=f"https://github.com/{request.repo_full_name}/issues/501",
            labels=request.labels,
            simulated=True,
        )

    async def create_branch_ref(
        self,
        repo_full_name: str,
        new_branch: str,
        base_sha: str,
        token: Optional[str] = None,
        force_offline: bool = False,
    ) -> Dict[str, Any]:
        """Create a new Git branch reference (`refs/heads/<new_branch>`) on GitHub."""
        ref_name = f"refs/heads/{new_branch}" if not new_branch.startswith("refs/") else new_branch
        resolved_token = self.resolve_oauth_token(token)

        if not force_offline and resolved_token:
            headers = self.build_headers(resolved_token)
            url = f"{GITHUB_API_BASE_URL}/repos/{repo_full_name}/git/refs"
            payload = {"ref": ref_name, "sha": base_sha}
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 201:
                    data = resp.json()
                    return {
                        "ref": data.get("ref", ref_name),
                        "sha": (data.get("object") or {}).get("sha", base_sha),
                        "simulated": False,
                    }
            except Exception as exc:
                logger.warning(f"GitHub branch creation failed: {exc}")

        return {
            "ref": ref_name,
            "sha": base_sha,
            "simulated": True,
        }

    async def create_draft_pull_request(
        self,
        request: GitHubDraftPRCreateRequest,
        token: Optional[str] = None,
        force_offline: bool = False,
    ) -> GitHubDraftPRResult:
        """Open a Draft Pull Request on GitHub containing human-approved auto-fix patches."""
        resolved_token = self.resolve_oauth_token(token)
        if not force_offline and resolved_token:
            headers = self.build_headers(resolved_token)
            url = f"{GITHUB_API_BASE_URL}/repos/{request.repo_full_name}/pulls"
            payload = {
                "title": request.title,
                "body": request.body,
                "head": request.head_branch,
                "base": request.base_branch,
                "draft": request.draft,
            }
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 201:
                    data = resp.json()
                    return GitHubDraftPRResult(
                        pr_number=int(data.get("number", 1)),
                        repo_full_name=request.repo_full_name,
                        title=data.get("title", request.title),
                        head_branch=request.head_branch,
                        base_branch=request.base_branch,
                        draft=bool(data.get("draft", request.draft)),
                        html_url=data.get(
                            "html_url",
                            f"https://github.com/{request.repo_full_name}/pull/1",
                        ),
                        simulated=False,
                    )
            except Exception as exc:
                logger.warning(f"GitHub draft PR creation failed: {exc}")

        return GitHubDraftPRResult(
            pr_number=701,
            repo_full_name=request.repo_full_name,
            title=request.title,
            head_branch=request.head_branch,
            base_branch=request.base_branch,
            draft=request.draft,
            html_url=f"https://github.com/{request.repo_full_name}/pull/701",
            simulated=True,
        )


github_client_service = GitHubAPIClient()
