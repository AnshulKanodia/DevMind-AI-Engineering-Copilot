from typing import Any, Dict
from fastapi import APIRouter, status

from app.core.guardrails import token_guardrail

router = APIRouter()


@router.get("/usage/{repo_id}")
async def get_repo_token_usage(repo_id: str) -> Dict[str, Any]:
    """Retrieve cumulative token consumption, dollar spend, and remaining quota for a repository."""
    return token_guardrail.get_usage(repo_id)


@router.post("/reset/{repo_id}", status_code=status.HTTP_200_OK)
async def reset_repo_token_usage(repo_id: str) -> Dict[str, str]:
    """Reset token usage accounting for a repository."""
    token_guardrail.reset_usage(repo_id)
    return {"status": "reset", "repo_id": repo_id}
