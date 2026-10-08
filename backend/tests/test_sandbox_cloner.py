import pytest
from pathlib import Path
from fastapi import HTTPException
from app.services.sandbox_manager import SandboxManager
from app.services.git_cloner import git_cloner_service
from app.schemas.repository import RepoCloneRequest


def test_sandbox_path_resolution_and_traversal_prevention(tmp_path):
    mgr = SandboxManager(base_dir=str(tmp_path))
    
    # Valid ID resolution
    repo_id, sandbox_dir = mgr.create_sandbox()
    assert sandbox_dir.exists()
    assert str(sandbox_dir).startswith(str(tmp_path))

    # Path traversal attack attempt with ../ should be blocked or sanitized
    attack_id = "../../etc/passwd"
    sanitized_path = mgr.get_sandbox_path(attack_id)
    # basename extracts passwd, resolving safely inside base_dir
    assert str(sanitized_path).startswith(str(tmp_path))

    # Cleanup verification
    assert mgr.cleanup_sandbox(repo_id) is True
    assert not sandbox_dir.exists()


def test_sandbox_quota_enforcement(tmp_path):
    mgr = SandboxManager(base_dir=str(tmp_path))
    repo_id, sandbox_dir = mgr.create_sandbox()

    # Create dummy files
    dummy_file = sandbox_dir / "large_file.bin"
    dummy_file.write_bytes(b"A" * 1024 * 100)  # 100 KB

    size = mgr.check_size_quota(sandbox_dir)
    assert size >= 100 * 1024

    # Cleanup
    mgr.cleanup_sandbox(repo_id)


def test_git_token_masking_in_urls():
    raw_url = "https://github.com/octocat/Hello-World.git"
    secret_token = "ghp_1234567890SECRET_PAT"

    auth_url, display_url = git_cloner_service._prepare_authenticated_url(raw_url, secret_token)

    # Auth URL contains the token for git access
    assert secret_token in auth_url
    assert "x-access-token" in auth_url

    # Display URL MUST NOT contain the token
    assert secret_token not in display_url
    assert "***@github.com" in display_url
