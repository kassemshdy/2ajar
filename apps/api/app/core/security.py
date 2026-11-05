import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # argon2id with library defaults
_COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "1234567890",
    "12345678910",
    "qwertyuiop",
    "azertyuiop",
    "iloveyou12",
    "lebanon123",
    "beirut1234",
    "admin12345",
    "welcome123",
    "letmein123",
}

JWT_ALG = "HS256"


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Used to keep login timing similar when the email is unknown.
DUMMY_PASSWORD_HASH = _hasher.hash("dummy-password-for-timing")


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("Password must be at least 10 characters")
    if len(password) > 128:
        problems.append("Password must be at most 128 characters")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("Password is too common")
    return problems


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    s = get_settings()
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_ttl_minutes),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    return payload


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
