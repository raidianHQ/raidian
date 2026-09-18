"""Tests for the User model (Step 22,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 3).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.models import User
from tests.factories import make_user


def test_creating_a_user_succeeds_and_is_retrievable(db_session):
    user = make_user(db_session, email="alice@example.com")
    db_session.commit()

    reloaded = db_session.get(User, user.id)
    assert reloaded.email == "alice@example.com"
    assert reloaded.is_active is True  # default
    assert reloaded.created_at is not None
    assert reloaded.updated_at is not None


def test_hashed_password_is_not_the_plaintext(db_session):
    user = make_user(db_session, password="correct horse battery staple")
    assert user.hashed_password != "correct horse battery staple"


def test_password_hash_verifies_the_correct_password(db_session):
    user = make_user(db_session, password="correct horse battery staple")
    assert verify_password("correct horse battery staple", user.hashed_password) is True


def test_password_hash_rejects_an_incorrect_password(db_session):
    user = make_user(db_session, password="correct horse battery staple")
    assert verify_password("wrong password entirely", user.hashed_password) is False


def test_is_active_can_be_set_false(db_session):
    user = make_user(db_session, email="inactive@example.com", is_active=False)
    db_session.commit()

    reloaded = db_session.get(User, user.id)
    assert reloaded.is_active is False


def test_duplicate_email_violates_the_unique_constraint(db_session):
    make_user(db_session, email="dup@example.com")
    db_session.commit()

    duplicate = User(email="dup@example.com", hashed_password=hash_password("irrelevant"))
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
