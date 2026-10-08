import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, status

from app.core.config import get_settings


def _remove_readonly(func, path, excinfo):
    """Error handler for Windows read-only files in git directories during cleanup."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class SandboxManager:
    """Manages ephemeral sandboxed directories for secure repository isolation."""

    def __init__(self, base_dir: Optional[str] = None):
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.SANDBOX_TEMP_DIR).resolve()
        self.max_size_bytes = settings.MAX_REPO_SIZE_MB * 1024 * 1024
        self._ensure_base_directory()

    def _ensure_base_directory(self) -> None:
        """Create base sandbox directory if it doesn't already exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def generate_repo_id(self) -> str:
        """Generate a cryptographically random, collision-resistant repository session identifier."""
        return str(uuid.uuid4())

    def get_sandbox_path(self, repo_id: str) -> Path:
        """Resolve and strictly validate the ephemeral sandbox directory path.
        
        Prevents path traversal attacks (e.g., ../../../etc).
        """
        clean_id = os.path.basename(repo_id.strip())
        target_path = (self.base_dir / clean_id).resolve()

        if not str(target_path).startswith(str(self.base_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Path traversal attempted in repository ID.",
            )
        return target_path

    def create_sandbox(self, repo_id: Optional[str] = None) -> Tuple[str, Path]:
        """Create a fresh isolated directory for a repository clone."""
        r_id = repo_id or self.generate_repo_id()
        sandbox_path = self.get_sandbox_path(r_id)

        if sandbox_path.exists():
            self.cleanup_sandbox(r_id)

        sandbox_path.mkdir(parents=True, exist_ok=False)
        return r_id, sandbox_path

    def cleanup_sandbox(self, repo_id: str) -> bool:
        """Safely delete the ephemeral sandbox directory."""
        sandbox_path = self.get_sandbox_path(repo_id)
        if sandbox_path.exists():
            try:
                shutil.rmtree(sandbox_path, onerror=_remove_readonly)
                return True
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to cleanup sandbox directory {repo_id}: {str(e)}",
                )
        return False

    def check_size_quota(self, sandbox_path: Path) -> int:
        """Calculate total directory disk usage and enforce maximum allowed quota."""
        total_size = 0
        for dirpath, _, filenames in os.walk(sandbox_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)

        if total_size > self.max_size_bytes:
            # Over quota: delete immediately
            shutil.rmtree(sandbox_path, onerror=_remove_readonly)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Repository exceeds maximum allowed size quota of {self.max_size_bytes // (1024*1024)} MB.",
            )
        return total_size


sandbox_manager = SandboxManager()
