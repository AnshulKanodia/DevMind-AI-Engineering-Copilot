from pathlib import Path
import pytest


def get_repo_root() -> Path:
    """Resolve the repository root directory."""
    current = Path(__file__).resolve().parent.parent
    if (current / "frontend").exists():
        return current
    if (current.parent / "frontend").exists():
        return current.parent
    return Path.cwd()


def test_backend_dockerfile_security_and_stages():
    """Verify backend Dockerfile implements multi-stage build, non-root user, and healthcheck."""
    root = get_repo_root()
    dockerfile = root / "backend" / "Dockerfile"
    assert dockerfile.exists(), f"Backend Dockerfile missing at {dockerfile}"

    content = dockerfile.read_text(encoding="utf-8")

    # Multi-stage build verification
    assert "FROM python:3.11-slim AS builder" in content
    assert "FROM python:3.11-slim AS runner" in content

    # Non-root user security hardening
    assert "useradd" in content
    assert "appuser" in content
    assert "USER appuser" in content

    # Sandbox directory isolation
    assert "/tmp/devmind-sandboxes" in content

    # Healthcheck verification
    assert "HEALTHCHECK" in content
    assert "http://localhost:8000/health" in content

    # Expose and launch
    assert "EXPOSE 8000" in content
    assert 'CMD ["uvicorn", "app.main:app"' in content


def test_frontend_dockerfile_security_and_stages():
    """Verify frontend Dockerfile implements multi-stage build, non-root nextjs user, and standalone runner."""
    root = get_repo_root()
    dockerfile = root / "frontend" / "Dockerfile"
    assert dockerfile.exists(), f"Frontend Dockerfile missing at {dockerfile}"

    content = dockerfile.read_text(encoding="utf-8")

    # Multi-stage build verification
    assert "FROM node:20-alpine AS deps" in content
    assert "FROM node:20-alpine AS builder" in content
    assert "FROM node:20-alpine AS runner" in content

    # Non-root user security hardening
    assert "addgroup" in content
    assert "nextjs" in content
    assert "USER nextjs" in content

    # Standalone output copy
    assert ".next/standalone" in content

    # Healthcheck verification
    assert "HEALTHCHECK" in content
    assert "http://localhost:3000" in content

    # Expose and launch
    assert "EXPOSE 3000" in content
    assert 'CMD ["node", "server.js"]' in content


def test_dockerignore_coverage():
    """Verify backend and frontend .dockerignore files exclude sensitive files and tests."""
    root = get_repo_root()

    backend_ignore = (root / "backend" / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in backend_ignore
    assert ".git" in backend_ignore
    assert "tests/" in backend_ignore
    assert ".venv" in backend_ignore

    frontend_ignore = (root / "frontend" / ".dockerignore").read_text(encoding="utf-8")
    assert "node_modules" in frontend_ignore
    assert ".next" in frontend_ignore
    assert ".git" in frontend_ignore
    assert "tests/" in frontend_ignore
