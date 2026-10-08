import asyncio
import re
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import HTTPException, status

from app.schemas.git_metadata import (
    BranchDiffResponse,
    CommitHistoryResponse,
    CommitLogItem,
    FileDiffItem,
    GitTagItem,
    RepoTagsResponse,
)
from app.services.sandbox_manager import sandbox_manager


class GitMetadataService:
    """Service to query git metadata (commits, diffs, tags) from isolated repository sandboxes."""

    async def _run_git(
        self, cmd: List[str], cwd: Path, timeout: int = 30
    ) -> Tuple[str, str]:
        """Execute git command within target sandbox directory."""
        if not cwd.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sandbox path does not exist: {cwd}",
            )
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
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
                detail=f"Execution error: {str(e)}",
            )

        if process.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Git command failed: {err}",
            )

        return (
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def get_commit_history(
        self, repo_id: str, limit: int = 20, branch: Optional[str] = None
    ) -> CommitHistoryResponse:
        """Fetch git commit log history with author, date, and messages."""
        sandbox_path = sandbox_manager.get_sandbox_path(repo_id)
        target_branch = branch or "HEAD"

        # Format: %H (sha), %an (author name), %ae (email), %ad (date), %s (subject), %b (body), %x1e (record sep)
        cmd = [
            "git", "log", f"-n{limit}",
            "--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s%x09%b%x1e",
            "--date=iso",
            target_branch,
        ]

        stdout, _ = await self._run_git(cmd, sandbox_path)
        commits: List[CommitLogItem] = []

        if stdout:
            records = stdout.split("\x1e")
            for rec in records:
                rec = rec.strip()
                if not rec:
                    continue
                parts = rec.split("\t")
                if len(parts) >= 5:
                    sha = parts[0]
                    aname = parts[1]
                    aemail = parts[2]
                    adate = parts[3]
                    summary = parts[4]
                    body = parts[5].strip() if len(parts) > 5 else ""
                    full_msg = f"{summary}\n\n{body}".strip() if body else summary

                    commits.append(
                        CommitLogItem(
                            sha=sha,
                            author_name=aname,
                            author_email=aemail,
                            date_iso=adate,
                            summary=summary,
                            message=full_msg,
                        )
                    )

        return CommitHistoryResponse(
            repo_id=repo_id,
            branch=target_branch,
            total_returned=len(commits),
            commits=commits,
        )

    def parse_patch_files(self, diff_text: str, numstat_text: str) -> List[FileDiffItem]:
        """Parse git diff patch and numstat into structured FileDiffItem objects."""
        # Map numstat to counts: {path: (additions, deletions)}
        stat_map = {}
        for line in numstat_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=2)
            if len(parts) == 3:
                adds = int(parts[0]) if parts[0].isdigit() else 0
                dels = int(parts[1]) if parts[1].isdigit() else 0
                filepath = parts[2]
                stat_map[filepath] = (adds, dels)

        # Split diff by file header: diff --git a/... b/...
        file_diffs: List[FileDiffItem] = []
        raw_sections = re.split(r"(?=diff --git a/)", diff_text)

        for sec in raw_sections:
            sec = sec.strip()
            if not sec.startswith("diff --git"):
                continue

            # Extract paths from header: diff --git a/fileA b/fileB
            header_match = re.search(r"diff --git a/(\S+) b/(\S+)", sec)
            if not header_match:
                continue

            old_p = header_match.group(1)
            new_p = header_match.group(2)

            change_type = "modified"
            if "new file mode" in sec:
                change_type = "added"
            elif "deleted file mode" in sec:
                change_type = "deleted"
            elif "similarity index" in sec or "rename from" in sec:
                change_type = "renamed"

            adds, dels = stat_map.get(new_p, stat_map.get(old_p, (0, 0)))

            file_diffs.append(
                FileDiffItem(
                    old_path=old_p if change_type != "added" else None,
                    new_path=new_p,
                    change_type=change_type,
                    additions=adds,
                    deletions=dels,
                    patch_text=sec,
                )
            )

        return file_diffs

    async def get_branch_diff(
        self, repo_id: str, base_ref: str, target_ref: str
    ) -> BranchDiffResponse:
        """Calculate unified diff and change statistics between two refs or branches."""
        sandbox_path = sandbox_manager.get_sandbox_path(repo_id)

        # Retrieve numstat for additions/deletions
        numstat_cmd = ["git", "diff", "--numstat", f"{base_ref}..{target_ref}"]
        numstat_out, _ = await self._run_git(numstat_cmd, sandbox_path)

        # Retrieve full unified diff patches
        diff_cmd = ["git", "diff", "-p", f"{base_ref}..{target_ref}"]
        diff_out, _ = await self._run_git(diff_cmd, sandbox_path)

        files = self.parse_patch_files(diff_out, numstat_out)
        total_adds = sum(f.additions for f in files)
        total_dels = sum(f.deletions for f in files)

        return BranchDiffResponse(
            repo_id=repo_id,
            base_ref=base_ref,
            target_ref=target_ref,
            total_files_changed=len(files),
            total_additions=total_adds,
            total_deletions=total_dels,
            files=files,
        )

    async def get_tags(self, repo_id: str) -> RepoTagsResponse:
        """List all git tags and associated release notes."""
        sandbox_path = sandbox_manager.get_sandbox_path(repo_id)

        cmd = [
            "git", "tag", "-l",
            "--format=%(refname:short)%x09%(objectname)%x09%(contents:subject)",
        ]
        stdout, _ = await self._run_git(cmd, sandbox_path)
        tags: List[GitTagItem] = []

        if stdout:
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    name = parts[0]
                    sha = parts[1]
                    msg = parts[2] if len(parts) > 2 else ""
                    tags.append(GitTagItem(name=name, commit_sha=sha, message=msg))

        return RepoTagsResponse(
            repo_id=repo_id,
            total_tags=len(tags),
            tags=tags,
        )


git_metadata_service = GitMetadataService()
