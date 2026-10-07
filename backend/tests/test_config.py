from app.core.config import Settings, get_settings
from app.core.security import encrypt_token, decrypt_token, create_access_token, decode_access_token


def test_settings_defaults():
    settings = get_settings()
    assert settings.PROJECT_NAME == "DevMind"
    assert settings.ENVIRONMENT in ["development", "staging", "production"]
    assert isinstance(settings.BACKEND_CORS_ORIGINS, list)
    assert settings.OPENAI_EMBEDDING_DIMENSIONS == 1536


def test_cors_validator_formats():
    # Test comma-separated string
    s1 = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000,http://app.devmind.local")
    assert "http://localhost:3000" in s1.BACKEND_CORS_ORIGINS
    assert "http://app.devmind.local" in s1.BACKEND_CORS_ORIGINS

    # Test JSON string
    s2 = Settings(BACKEND_CORS_ORIGINS='["http://localhost:3000"]')
    assert s2.BACKEND_CORS_ORIGINS == ["http://localhost:3000"]


def test_token_encryption_roundtrip():
    sample_github_token = "gho_1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted = encrypt_token(sample_github_token)
    assert encrypted != sample_github_token
    decrypted = decrypt_token(encrypted)
    assert decrypted == sample_github_token


def test_jwt_access_token_creation_and_verification():
    user_id = "user_github_998877"
    token = create_access_token(subject=user_id, claims={"role": "developer"})
    decoded = decode_access_token(token)

    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["role"] == "developer"
    assert "exp" in decoded
