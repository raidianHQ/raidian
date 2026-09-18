"""Request/response schemas for the Authentication API (Step 22; password
byte-length validation added in Step 23). See
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 5/7.

email is validated with a minimal, dependency-free shape check rather than
Pydantic's EmailStr, which requires installing the separate
`email-validator` package -- not among the smallest-dependency-set
additions that document authorizes (Section 12); a full RFC-5322 parser is
not needed to satisfy this project's actual requirement (reject obviously
malformed input).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# bcrypt (app/core/security.py) hard-limits its input to 72 bytes and
# raises ValueError beyond that. Rejected here, at the request-validation
# boundary, as a clean 422 (FastAPI's existing validation-error shape) --
# never truncated, and never allowed to reach hash_password()/
# verify_password() and crash with a 500 (Step 23 remediation of a Step 22
# defect confirmed against both registration and login, since
# verify_password() calls bcrypt.checkpw(), which has the identical limit).
_BCRYPT_MAX_PASSWORD_BYTES = 72


def _reject_passwords_bcrypt_cannot_use(value: str) -> str:
    if len(value.encode("utf-8")) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password must not exceed {_BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded"
        )
    return value


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email_shape(cls, value: str) -> str:
        value = value.strip()
        local, _, domain = value.partition("@")
        if not local or not domain or "@" in domain or " " in value or "." not in domain:
            raise ValueError("email must be a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def _validate_password_byte_length(cls, value: str) -> str:
        return _reject_passwords_bcrypt_cannot_use(value)


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def _validate_password_byte_length(cls, value: str) -> str:
        return _reject_passwords_bcrypt_cannot_use(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
