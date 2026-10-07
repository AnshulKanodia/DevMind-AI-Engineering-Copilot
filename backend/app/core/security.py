import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings

ALGORITHM = "HS256"


def get_fernet_cipher(key: Optional[str] = None) -> Fernet:
    """Initialize a Fernet cipher instance from the configured encryption key.
    
    If the key is not already a valid 32-byte url-safe base64 string, derives one using PBKDF2.
    """
    settings = get_settings()
    raw_key = key or settings.ENCRYPTION_KEY

    try:
        # Validate if key is already a valid Fernet key
        return Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
    except Exception:
        # Derive a valid 32-byte base64 Fernet key using KDF
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"devmind_token_salt",
            iterations=100_000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
        return Fernet(derived_key)


def encrypt_token(plain_token: str) -> str:
    """Encrypt sensitive OAuth tokens before database storage."""
    cipher = get_fernet_cipher()
    encrypted_bytes = cipher.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt stored OAuth tokens for internal API usage."""
    cipher = get_fernet_cipher()
    decrypted_bytes = cipher.decrypt(encrypted_token.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token for user authentication."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    if claims:
        payload.update(claims)
        
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
