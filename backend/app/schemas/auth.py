from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class GitHubOAuthCallbackRequest(BaseModel):
    code: str = Field(..., description="Authorization code returned by GitHub OAuth")
    state: Optional[str] = Field(None, description="CSRF state parameter")


class GitHubUserPayload(BaseModel):
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None


class UserBase(BaseModel):
    github_id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: Optional[str] = None
    is_active: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class OAuthURLResponse(BaseModel):
    authorization_url: str
