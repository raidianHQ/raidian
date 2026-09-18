"""Password hashing and JWT issuance/verification (Step 22).

Kept separate from app/api/ and app/services/ -- these are pure,
DB-independent primitives (hash/verify a password string; encode/decode a
token payload), reused by both the auth service
(app/services/auth_service.py) and the API-layer dependency
(app/api/dependencies.py::get_current_user). See
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Sections
5-7.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


class InvalidTokenError(ValueError):
    """Raised for any malformed, expired, invalid-signature, or
    subject-less/malformed-subject access token -- callers (currently only
    app/api/dependencies.py::get_current_user) map this to a single,
    uniform 401 regardless of which specific condition triggered it.
    """


def hash_password(password: str) -> str:
    """Never store the return value's input (plaintext) anywhere -- only
    this hash. bcrypt.gensalt() produces a fresh, random salt per call.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Constant-time comparison via bcrypt's own checkpw -- never a manual
    `==` on the hash or the plaintext.
    """
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: UUID) -> str:
    """Issues a short-lived JWT whose only claims are `sub` (the User.id),
    `iat`, and `exp` -- no refresh token, no issuer/audience (this project
    has exactly one API audience). See
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 7.1.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    """Decodes and verifies a JWT, returning its subject as a User id.

    The expected algorithm is passed explicitly (`algorithms=[...]`) so
    the token's own, attacker-controlled `alg` header is never trusted --
    this is the specific algorithm-confusion mitigation
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 9.2 names as a required implementation discipline, not an
    optional hardening step.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("token is malformed, expired, or has an invalid signature") from exc

    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("token has no subject claim")
    try:
        return UUID(subject)
    except ValueError as exc:
        raise InvalidTokenError("token subject is not a valid user id") from exc
