"""
Security, Cryptography, and Token Utilities.
Uses Argon2id for password hashing, HS256 JWTs for access tokens,
and SHA-256 for secure hashing of opaque database tokens.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Argon2id password hasher with RFC 9106 recommended parameters
pwd_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash with constant-time comparison."""
    try:
        return pwd_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False
    except Exception as exc:
        logger.error("Unexpected error verifying password", error=str(exc))
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except jwt.PyJWTError as exc:
        logger.debug("Access token decoding failed", error=str(exc))
        return None


def generate_secure_token(length_bytes: int = 32) -> str:
    """Generate a high-entropy URL-safe cryptographic token string."""
    return secrets.token_urlsafe(length_bytes)


def hash_token(token: str) -> str:
    """
    Compute SHA-256 hash of an opaque token.
    Used for storing refresh tokens, verification tokens, and reset tokens safely.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
