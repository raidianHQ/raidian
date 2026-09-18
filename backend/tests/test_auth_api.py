"""API tests for the Authentication API (Step 22,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
5/7).

Self-contained fixtures, mirroring test_api_interpretation.py's own
established rationale: a `client` fixture needs a `get_db` override bound
to a StaticPool-backed in-memory SQLite engine.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import decode_access_token
from app.db.session import get_db
from app.main import app
from app.models import Base, User


@pytest.fixture()
def api_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def api_session_factory(api_engine):
    return sessionmaker(bind=api_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def client(api_session_factory):
    def _override_get_db():
        db = api_session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- POST /auth/register -----------------------------------------------------------


def test_register_returns_201_and_never_exposes_the_password_hash(client):
    response = client.post(
        "/auth/register", json={"email": "new@example.com", "password": "correct horse battery"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "id" in body and "created_at" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_rejects_a_duplicate_email(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password1234"})

    response = client.post("/auth/register", json={"email": "dup@example.com", "password": "password5678"})

    assert response.status_code == 409


def test_register_rejects_a_duplicate_email_case_insensitively(client):
    client.post("/auth/register", json={"email": "Mixed@Example.com", "password": "password1234"})

    response = client.post("/auth/register", json={"email": "mixed@example.com", "password": "password5678"})

    assert response.status_code == 409


def test_register_rejects_a_malformed_email(client):
    response = client.post("/auth/register", json={"email": "not-an-email", "password": "password1234"})
    assert response.status_code == 422


def test_register_rejects_a_too_short_password(client):
    response = client.post("/auth/register", json={"email": "short@example.com", "password": "short"})
    assert response.status_code == 422


# --- Password byte-length boundary (Step 23 remediation of the bcrypt 72-byte defect) --


def test_register_accepts_a_password_at_exactly_the_72_byte_boundary(client):
    password = "a" * 72
    assert len(password.encode("utf-8")) == 72  # sanity: exactly at the limit, not over it

    response = client.post("/auth/register", json={"email": "boundary72@example.com", "password": password})

    assert response.status_code == 201


def test_register_cleanly_rejects_a_73_byte_ascii_password(client):
    password = "a" * 73
    assert len(password.encode("utf-8")) == 73  # sanity: one byte over the limit

    response = client.post("/auth/register", json={"email": "over73@example.com", "password": password})

    assert response.status_code == 422


def test_register_cleanly_rejects_a_multibyte_password_under_72_characters_but_over_72_bytes(client):
    password = "\U0001f512" * 30  # a 4-byte-in-UTF-8 emoji, repeated
    assert len(password) < 72  # sanity: well under the character-based Field bound
    assert len(password.encode("utf-8")) > 72  # sanity: this is genuinely the multibyte case

    response = client.post("/auth/register", json={"email": "multibyte@example.com", "password": password})

    assert response.status_code == 422


def test_register_with_an_ordinary_password_is_unaffected_by_the_byte_length_check(client):
    response = client.post(
        "/auth/register", json={"email": "ordinary@example.com", "password": "correct horse battery"}
    )
    assert response.status_code == 201


def test_login_accepts_a_password_at_exactly_the_72_byte_boundary(client):
    password = "b" * 72
    client.post("/auth/register", json={"email": "loginboundary@example.com", "password": password})

    response = client.post("/auth/login", json={"email": "loginboundary@example.com", "password": password})

    assert response.status_code == 200


def test_login_cleanly_rejects_a_73_byte_ascii_password(client):
    """verify_password() calls bcrypt.checkpw(), which has the identical
    72-byte limit hash_password()/bcrypt.hashpw() has -- login is just as
    exposed to the same underlying defect as registration, so it gets the
    identical schema-level fix (app/schemas/auth.py::LoginRequest).
    """
    response = client.post(
        "/auth/login", json={"email": "whoever@example.com", "password": "a" * 73}
    )
    assert response.status_code == 422


def test_login_with_an_ordinary_password_is_unaffected_by_the_byte_length_check(client):
    client.post("/auth/register", json={"email": "ordinarylogin@example.com", "password": "correct horse battery"})

    response = client.post(
        "/auth/login", json={"email": "ordinarylogin@example.com", "password": "correct horse battery"}
    )
    assert response.status_code == 200


# --- POST /auth/login ---------------------------------------------------------------


def test_login_succeeds_with_correct_credentials_and_returns_a_valid_token(client):
    client.post("/auth/register", json={"email": "login@example.com", "password": "correct horse battery"})

    response = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "correct horse battery"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    decode_access_token(body["access_token"])  # does not raise


def test_login_rejects_an_incorrect_password(client):
    client.post("/auth/register", json={"email": "wrongpass@example.com", "password": "correct horse battery"})

    response = client.post("/auth/login", json={"email": "wrongpass@example.com", "password": "incorrect"})
    assert response.status_code == 401


def test_login_rejects_a_nonexistent_account(client):
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert response.status_code == 401


def test_login_rejects_an_inactive_account(client, api_session_factory):
    client.post("/auth/register", json={"email": "inactive@example.com", "password": "correct horse battery"})

    session = api_session_factory()
    user = session.query(User).filter_by(email="inactive@example.com").one()
    user.is_active = False
    session.commit()
    session.close()

    response = client.post(
        "/auth/login", json={"email": "inactive@example.com", "password": "correct horse battery"}
    )
    assert response.status_code == 401


def test_login_failure_responses_do_not_distinguish_wrong_password_from_no_such_account(client):
    client.post("/auth/register", json={"email": "exists@example.com", "password": "correct horse battery"})

    wrong_password = client.post("/auth/login", json={"email": "exists@example.com", "password": "incorrect"})
    no_account = client.post("/auth/login", json={"email": "nobody-else@example.com", "password": "incorrect"})

    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json()["detail"] == no_account.json()["detail"]
