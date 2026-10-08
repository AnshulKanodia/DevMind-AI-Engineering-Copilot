import os
import subprocess
from pathlib import Path
import pytest

from app.services.file_filter import file_filter_service
from app.services.git_metadata import git_metadata_service
from app.services.sandbox_manager import SandboxManager
from app.services.secrets_sanitizer import secrets_sanitizer_service


@pytest.fixture
def mock_git_repo(tmp_path):
    """Fixture that initializes a realistic local Git repository with mixed code, secrets, and noise."""
    repo_dir = tmp_path / "sample_project"
    repo_dir.mkdir()

    # Initialize a real Git repository in tmp_path
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test Developer"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@devmind.ai"], cwd=repo_dir, capture_output=True, check=True)

    # 1. Valid source code
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\ndef multiply(a: int, b: int) -> int:\n    return a * b\n",
        encoding="utf-8"
    )
    (src_dir / "client.ts").write_text(
        "export interface User {\n    id: string;\n    name: string;\n}\n",
        encoding="utf-8"
    )

    # 2. File with secrets
    (src_dir / "auth_config.py").write_text(
        'AWS_SECRET_KEY = "AKIA1234567890ABCDEF"\nOPENAI_KEY = "sk-proj-9876543210abcdef9876543210abcdef9876543210abcdef"\n',
        encoding="utf-8"
    )

    # 3. Noise directories to be ignored
    nm_dir = repo_dir / "node_modules" / "express"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("module.exports = {};", encoding="utf-8")

    dist_dir = repo_dir / "dist"
    dist_dir.mkdir()
    (dist_dir / "bundle.min.js").write_text("function min(){}", encoding="utf-8")

    # 4. Ignored files & binaries
    (repo_dir / "package-lock.json").write_text('{"lockfileVersion": 3}', encoding="utf-8")
    (repo_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00\x01\x00\x10\x10")

    # Initial Git Commit
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit of sample project"], cwd=repo_dir, capture_output=True, check=True)

    # Second commit to generate diff history
    (src_dir / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\ndef multiply(a: int, b: int) -> int:\n    return a * b\n\ndef subtract(a: int, b: int) -> int:\n    return a - b\n",
        encoding="utf-8"
    )
    subprocess.run(["git", "add", "src/calculator.py"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "feat: add subtract function to calculator"], cwd=repo_dir, capture_output=True, check=True)

    return repo_dir


def test_end_to_end_file_filter_pipeline(mock_git_repo):
    """Verify that file filter isolates strictly eligible source files while pruning all noise."""
    summary = file_filter_service.scan_repository(mock_git_repo)

    # Total eligible source files should be 3: calculator.py, client.ts, auth_config.py
    assert summary.eligible_count == 3
    rel_paths = {f.relative_path for f in summary.eligible_files}
    assert "src/calculator.py" in rel_paths
    assert "src/client.ts" in rel_paths
    assert "src/auth_config.py" in rel_paths

    # Noise files must NOT be in eligible list
    assert "node_modules/express/index.js" not in rel_paths
    assert "dist/bundle.min.js" not in rel_paths
    assert "package-lock.json" not in rel_paths
    assert "favicon.ico" not in rel_paths

    assert summary.total_code_lines > 0
    assert summary.skipped_count >= 4


def test_end_to_end_secrets_audit_and_redaction(mock_git_repo):
    """Verify scanning and in-place redacting of credentials inside a repository."""
    auth_file = mock_git_repo / "src" / "auth_config.py"

    # Step 1: Scan and identify secrets
    result = secrets_sanitizer_service.sanitize_file(auth_file, in_place=True)
    assert result.findings_count == 2

    types = {f.secret_type for f in result.findings}
    assert "aws_access_key" in types
    assert "openai_api_key" in types

    # Step 2: Verify in-place redaction on disk
    updated_content = auth_file.read_text(encoding="utf-8")
    assert "AKIA1234567890ABCDEF" not in updated_content
    assert "sk-proj-" not in updated_content
    assert "[REDACTED_SECRET:AWS_ACCESS_KEY]" in updated_content
    assert "[REDACTED_SECRET:OPENAI_API_KEY]" in updated_content

    # Step 3: Re-scan should report zero remaining secrets
    clean_check = secrets_sanitizer_service.sanitize_file(auth_file, in_place=False)
    assert clean_check.findings_count == 0


@pytest.mark.asyncio
async def test_end_to_end_git_metadata_pipeline(mock_git_repo, tmp_path):
    """Verify git commit history extraction and branch diff calculations."""
    sandbox_mgr = SandboxManager(base_dir=str(tmp_path))
    repo_id = mock_git_repo.name

    # Point sandbox to mock repo
    history = await git_metadata_service.get_commit_history(repo_id=repo_id, limit=5)
    # The fixture created 2 commits
    assert history.total_returned == 2
    assert "add subtract function" in history.commits[0].summary
    assert "initial commit" in history.commits[1].summary

    # Diff against previous commit
    diff_resp = await git_metadata_service.get_branch_diff(
        repo_id=repo_id,
        base_ref="HEAD~1",
        target_ref="HEAD"
    )
    assert diff_resp.total_files_changed == 1
    assert diff_resp.files[0].new_path == "src/calculator.py"
    assert diff_resp.files[0].additions >= 3
