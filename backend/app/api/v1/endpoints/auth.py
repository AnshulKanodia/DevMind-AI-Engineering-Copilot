from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user_claims
from app.schemas.auth import (
    GitHubOAuthCallbackRequest,
    OAuthURLResponse,
    TokenResponse,
    UserResponse,
)
from app.services.github_auth import github_auth_service

router = APIRouter()


@router.get(
    "/login",
    response_model=OAuthURLResponse,
    summary="Get GitHub OAuth Authorization URL",
    description="Generates the GitHub OAuth authorization URL with requested repo and user scopes.",
)
async def login(state: Optional[str] = Query(None, description="Optional CSRF state token")):
    auth_url = github_auth_service.get_authorization_url(state=state)
    return OAuthURLResponse(authorization_url=auth_url)


@router.post(
    "/callback",
    response_model=TokenResponse,
    summary="GitHub OAuth Callback (JSON Body)",
    description="Exchanges GitHub authorization code for token, stores encrypted token, and returns DevMind session JWT.",
)
async def auth_callback(payload: GitHubOAuthCallbackRequest):
    result = await github_auth_service.authenticate_github_user(payload.code)
    return result["session"]


@router.get(
    "/callback",
    response_model=TokenResponse,
    summary="GitHub OAuth Callback (Query Param Redirect)",
    description="Alternative GET handler for browser redirects after user authorizes on GitHub.",
)
async def auth_callback_redirect(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: Optional[str] = Query(None, description="CSRF state from GitHub"),
):
    result = await github_auth_service.authenticate_github_user(code)
    return result["session"]


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current Authenticated User",
    description="Returns user details encoded within the valid session JWT token.",
)
async def get_me(claims: dict = Depends(get_current_user_claims)):
    return UserResponse(
        id=claims.get("sub"),
        github_id=claims.get("github_id", 0),
        username=claims.get("username", "unknown"),
        name=claims.get("username"),
        is_active=True,
    )
