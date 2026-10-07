import pytest
from unittest.mock import patch, MagicMock
from app.services.github_auth import github_auth_service
from app.core.security import create_access_token, decode_access_token, encrypt_token, decrypt_token
from app.schemas.auth import GitHubUserPayload


def test_github_auth_url_generation():
    auth_url = github_auth_service.get_authorization_url(state="test_csrf_token_123")
    assert "https://github.com/login/oauth/authorize" in auth_url
    assert "scope=" in auth_url
    assert "state=test_csrf_token_123" in auth_url
    assert "redirect_uri=" in auth_url


def test_token_encryption_security():
    sample_pat = "gho_SAMPLE_PAT_SECRET_ABC1234567890"
    encrypted = encrypt_token(sample_pat)
    assert encrypted != sample_pat
    # Ensure decrypted value restores the token accurately
    decrypted = decrypt_token(encrypted)
    assert decrypted == sample_pat


def test_jwt_session_token_claims():
    user_id = "12345"
    token = create_access_token(
        subject=user_id,
        claims={"username": "octocat", "github_id": 12345}
    )
    claims = decode_access_token(token)
    assert claims is not None
    assert claims["sub"] == user_id
    assert claims["username"] == "octocat"
    assert claims["github_id"] == 12345


@pytest.mark.asyncio
async def test_authenticate_github_user_mocked():
    mock_gh_user = GitHubUserPayload(
        id=9999,
        login="octocat",
        name="The Octocat",
        email="octocat@github.com",
        avatar_url="https://github.com/images/error/octocat_happy.gif",
        html_url="https://github.com/octocat"
    )

    with patch.object(github_auth_service, "exchange_code_for_token", return_value="gho_mock_token_123"), \
         patch.object(github_auth_service, "get_github_user", return_value=mock_gh_user):
        
        result = await github_auth_service.authenticate_github_user("mock_code")
        assert "session" in result
        assert "encrypted_github_token" in result
        
        session = result["session"]
        assert session.user.username == "octocat"
        assert session.user.github_id == 9999
        assert session.access_token is not None

        # Verify decrypted token matches
        decrypted_token = decrypt_token(result["encrypted_github_token"])
        assert decrypted_token == "gho_mock_token_123"
