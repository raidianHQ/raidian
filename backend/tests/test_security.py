"""Tests for password hashing and JWT issuance/verification (Step 22,
app/core/security.py). See
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
5-7/9.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_a_value_distinct_from_the_input():
    assert hash_password("hunter2") != "hunter2"


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_password_rejects_an_incorrect_password():
    hashed = hash_password("hunter2")
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token_round_trips_the_subject():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_rejects_a_malformed_token():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt-at-all")


def test_decode_rejects_an_expired_token():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int((now - timedelta(minutes=60)).timestamp()),
        "exp": int((now - timedelta(minutes=30)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_rejects_a_token_with_an_invalid_signature():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    token = jwt.encode(payload, "a-completely-different-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_rejects_a_token_with_no_subject_claim():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=30)).timestamp())}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_rejects_a_token_whose_subject_is_not_a_valid_uuid():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "not-a-uuid",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_enforces_the_expected_algorithm_explicitly():
    """A token signed with a different algorithm than configured must be
    rejected -- proves the expected algorithm is passed to jwt.decode
    explicitly rather than trusting the token's own (attacker-controlled)
    `alg` header. This is the specific algorithm-confusion mitigation
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 9.2 names as a required implementation discipline.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS384")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
