"""Tests for app/services/auth_service.py (Step 22)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import verify_password
from app.models.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.services.auth_service import _is_duplicate_email_violation, authenticate_user, register_user
from tests.factories import make_user


def test_register_user_creates_a_user_with_a_hashed_password(db_session):
    user = register_user(db_session, email="Alice@Example.com", password="correct horse battery")
    db_session.commit()

    assert user.email == "alice@example.com"  # normalized lowercase
    assert user.hashed_password != "correct horse battery"
    assert verify_password("correct horse battery", user.hashed_password)


def test_register_user_rejects_a_duplicate_email_case_insensitively(db_session):
    register_user(db_session, email="dup@example.com", password="password12345")
    db_session.commit()

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(db_session, email="DUP@Example.com", password="anotherpassword")


def test_authenticate_user_succeeds_with_correct_credentials(db_session):
    register_user(db_session, email="bob@example.com", password="s3cret-password")
    db_session.commit()

    user = authenticate_user(db_session, email="bob@example.com", password="s3cret-password")
    assert user.email == "bob@example.com"


def test_authenticate_user_rejects_wrong_password(db_session):
    register_user(db_session, email="carol@example.com", password="right-password")
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, email="carol@example.com", password="wrong-password")


def test_authenticate_user_rejects_nonexistent_email(db_session):
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, email="nobody@example.com", password="whatever12345")


def test_authenticate_user_rejects_inactive_account(db_session):
    make_user(db_session, email="dave@example.com", password="right-password", is_active=False)
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, email="dave@example.com", password="right-password")


def test_register_user_converts_a_genuine_database_constraint_violation_to_the_same_domain_error(
    db_session, monkeypatch
):
    """Bypasses the pre-check (by making it blind to an already-committed
    row) so register_user()'s session.flush() itself hits the real
    users.email unique constraint -- proving the database constraint, not
    merely the pre-check, is the authoritative backstop
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 10.1 specifies (Step 23 remediation of the previously-uncaught
    IntegrityError this exact race could raise).
    """
    register_user(db_session, email="racer@example.com", password="password12345")
    db_session.commit()

    monkeypatch.setattr(
        "app.services.auth_service._find_existing_user_by_email", lambda session, email: None
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(db_session, email="racer@example.com", password="a-different-password")


def test_is_duplicate_email_violation_recognizes_the_actual_sqlite_message():
    exc = IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed: users.email"))
    assert _is_duplicate_email_violation(exc) is True


def test_is_duplicate_email_violation_recognizes_the_postgresql_message_shape():
    exc = IntegrityError(
        "INSERT ...",
        {},
        Exception('duplicate key value violates unique constraint "ix_users_email"\nDETAIL:  Key (email)=(x@example.com) already exists.'),
    )
    assert _is_duplicate_email_violation(exc) is True


def test_is_duplicate_email_violation_does_not_swallow_an_unrelated_integrity_error():
    """A constraint failure on some other column/table must not be
    silently reinterpreted as "email already registered" -- proves
    register_user()'s except-block re-raises anything this returns False
    for, rather than converting every IntegrityError unconditionally.
    """
    exc = IntegrityError("INSERT ...", {}, Exception("NOT NULL constraint failed: readings.question"))
    assert _is_duplicate_email_violation(exc) is False


def test_authenticate_user_failure_messages_are_identical_regardless_of_cause(db_session):
    """Enumeration-resistance: nonexistent email, wrong password, and an
    inactive account must all raise the identical error message
    (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 5.2's login-enumeration design).
    """
    make_user(db_session, email="erin@example.com", password="right-password", is_active=False)
    db_session.commit()

    messages = set()
    for email, password in [
        ("nobody@example.com", "whatever12345"),
        ("erin@example.com", "wrong-password"),
        ("erin@example.com", "right-password"),  # inactive
    ]:
        try:
            authenticate_user(db_session, email=email, password=password)
        except InvalidCredentialsError as exc:
            messages.add(str(exc))
    assert len(messages) == 1
