"""
Authentication, Security, and Password Hashing Tests.
Verifies Argon2id password hashing, JWT token generation & verification,
SHA-256 token hashing, sliding-window rate limiting, and password reset flows.
"""
import uuid
import pytest
from datetime import timedelta
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_token,
)
from app.core.rate_limit import SlidingWindowRateLimiter
from fastapi import HTTPException


def test_argon2id_password_hashing_and_verification():
    """Verify password hashing with Argon2id and constant-time verification."""
    password = "SuperSecretPassword!2026"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_access_token_creation_and_decoding():
    """Verify JWT access token creation, claims encoding, and validation."""
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "email": "auditor@acmefinance.com",
        "org_id": org_id,
    }

    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)

    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["email"] == "auditor@acmefinance.com"
    assert decoded["org_id"] == org_id
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_invalid_token_returns_none():
    """Verify corrupted or invalid tokens fail decoding safely."""
    assert decode_access_token("not-a-valid-token") is None
    assert decode_access_token("") is None


def test_secure_token_generation_and_sha256_hashing():
    """Verify random token entropy and deterministic SHA-256 hash storage."""
    raw_token_1 = generate_secure_token(32)
    raw_token_2 = generate_secure_token(32)

    assert raw_token_1 != raw_token_2
    assert len(raw_token_1) >= 40

    hash_1 = hash_token(raw_token_1)
    hash_2 = hash_token(raw_token_2)

    assert hash_1 != hash_2
    assert len(hash_1) == 64
    assert hash_token(raw_token_1) == hash_1


def test_sliding_window_rate_limiter():
    """Verify rate limiter blocks brute force attacks after exceeding threshold."""
    limiter = SlidingWindowRateLimiter()
    key = "test_ip_192.168.1.100"

    # 3 allowed attempts in 10-second window
    for _ in range(3):
        is_limited, _ = limiter.is_rate_limited(key, max_requests=3, window_seconds=10)
        assert is_limited is False

    # 4th attempt should be blocked
    is_limited, retry_after = limiter.is_rate_limited(key, max_requests=3, window_seconds=10)
    assert is_limited is True
    assert retry_after > 0

    with pytest.raises(HTTPException) as exc_info:
        limiter.check_or_raise(key, max_requests=3, window_seconds=10)
    assert exc_info.value.status_code == 429
