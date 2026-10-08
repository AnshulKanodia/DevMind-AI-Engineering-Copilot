import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.repository import RepoCloneRequest, RepoCloneResponse
from app.services.sandbox_manager import sandbox_manager


class GitClonerService:
    """Service to execute isolated git clone operations safely and securely."""

    def __init__(self):
        self.settings = get_settings()

    def _prepare_authenticated_url(self, repo_url: str, token: Optional[str]) -> Tuple[str, str]:
        """Inject authentication token into HTTPS URL securely while returning a sanitized display URL."""
        if not token or not repo_url.startswith("https://"):
            return repo_url, repo_url

        parsed = urlparse(repo_url)
        # Auth URL format: https://x-access-token:<token>@github.com/owner/repo.git
        netloc_with_token = f"x-access-token:{token}@{parsed.netloc}"
        auth_url = urlunparse(parsed._replace(netloc=netloc_with_token))

        # Redacted display URL format: https://***@github.com/owner/repo.git
        redacted_netloc = f"***@{parsed.netloc}"
        display_url = urlunparse(parsed._replace(netloc=redacted_netloc))

        return auth_url, display_url

    async def _run_git_command(
        self, cmd: list[str], cwd: Optional[Path] = None, timeout: int = 60
    ) -> Tuple[str, str]:
        """Execute a git CLI command as an isolated subprocess without using shell=True."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            if process:
                process.kill()
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Git command timed out after {timeout} seconds.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Subprocess execution error: {str(e)}",
            )

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            # Mask any token occurrence in error message
            if "x-access-token:" in error_msg:
                error_msg = error_msg.split("@")[-1]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Git command failed: {error_msg}",
            )

        return (
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def clone_repository(
        self, request: RepoCloneRequest, repo_id: Optional[str] = None
    ) -> RepoCloneResponse:
        """Execute secure git clone into an ephemeral sandbox directory."""
        start_time = time.time()
        r_id, sandbox_dir = sandbox_manager.create_sandbox(repo_id)

        auth_url, display_url = self._prepare_authenticated_url(
            request.repo_url, request.access_token
        )

        # Build git clone command line parameters
        clone_cmd = ["git", "clone"]
        if request.shallow:
            clone_cmd.extend(["--depth", "1"])
        if request.branch:
            clone_cmd.extend(["--branch", request.branch])

        clone_cmd.extend([auth_url, str(sandbox_dir)])

        try:
            # Execute clone
            await self._run_git_command(
                clone_cmd,
                timeout=self.settings.CLONE_TIMEOUT_SECONDS,
            )

            # Check disk usage against max size quota
            total_size = sandbox_manager.check_size_quota(sandbox_dir)

            # Retrieve latest commit SHA and message
            commit_sha, _ = await self._run_git_command(
                ["git", "rev-parse", "HEAD"], cwd=sandbox_dir, timeout=10
            )
            commit_msg, _ = await self._run_git_command(
                ["git", "log", "-1", "--pretty=%B"], cwd=sandbox_dir, timeout=10
            )

            # Count total source files
            file_count = 0
            for _, _, filenames in os.walk(sandbox_dir):
                file_count += len(filenames)

            duration = round(time.time() - start_time, 2)

            return RepoCloneResponse(
                repo_id=r_id,
                repo_url=display_url,
                branch=request.branch or "main",
                commit_sha=commit_sha,
                commit_message=commit_msg.strip(),
                sandbox_path=str(sandbox_dir),
                total_files=file_count,
                total_size_bytes=total_size,
                duration_seconds=duration,
                status="cloned",
            )

        except Exception as e:
            # Clean up corrupted or partially cloned directory
            sandbox_manager.cleanup_sandbox(r_id)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Repository clone error: {str(e)}",
            )


git_cloner_service = GitClonerService()
