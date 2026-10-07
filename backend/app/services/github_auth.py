import urllib.parse
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.security import encrypt_token, create_access_token
from app.schemas.auth import GitHubUserPayload, TokenResponse, UserResponse

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


class GitHubAuthService:
    """Service to manage GitHub OAuth authentication flows and secure token storage."""

    def __init__(self):
        self.settings = get_settings()

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Construct the GitHub OAuth login URL with requested scopes."""
        params = {
            "client_id": self.settings.GITHUB_CLIENT_ID,
            "redirect_uri": self.settings.GITHUB_REDIRECT_URI,
            "scope": "read:user user:email repo",
            "allow_signup": "true",
        }
        if state:
            params["state"] = state
        return f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange temporary OAuth code for a GitHub access token."""
        payload = {
            "client_id": self.settings.GITHUB_CLIENT_ID,
            "client_secret": self.settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": self.settings.GITHUB_REDIRECT_URI,
        }
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(GITHUB_TOKEN_URL, data=payload, headers=headers, timeout=15.0)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to retrieve access token from GitHub: {response.text}",
            )

        data = response.json()
        if "error" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth error: {data.get('error_description', data.get('error'))}",
            )

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access_token returned by GitHub",
            )
        return access_token

    async def get_github_user(self, access_token: str) -> GitHubUserPayload:
        """Fetch authenticated user profile details from GitHub API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DevMind-Copilot",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(GITHUB_USER_URL, headers=headers, timeout=15.0)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to fetch user profile from GitHub: {response.text}",
            )

        user_data = response.json()
        return GitHubUserPayload(**user_data)

    async def authenticate_github_user(self, code: str) -> Dict[str, Any]:
        """Perform full OAuth authentication exchange, encrypt credentials, and issue session JWT."""
        github_token = await self.exchange_code_for_token(code)
        gh_user = await self.get_github_user(github_token)

        # Encrypt GitHub token using AES/Fernet encryption for secure storage
        encrypted_gh_token = encrypt_token(github_token)

        # Prepare user profile
        user_info = UserResponse(
            id=str(gh_user.id),
            github_id=gh_user.id,
            username=gh_user.login,
            name=gh_user.name or gh_user.login,
            email=gh_user.email,
            avatar_url=gh_user.avatar_url,
            is_active=True,
        )

        # Issue DevMind session JWT
        jwt_token = create_access_token(
            subject=str(gh_user.id),
            claims={
                "username": gh_user.login,
                "github_id": gh_user.id,
            },
        )

        return {
            "session": TokenResponse(access_token=jwt_token, user=user_info),
            "encrypted_github_token": encrypted_gh_token,
        }


github_auth_service = GitHubAuthService()
