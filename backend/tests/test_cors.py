"""Tests for CORS middleware configuration (Step 41,
Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 3).

Exercises actual preflight and cross-origin response behavior via a
live TestClient against the real, configured app.add_middleware(...)
call in app/main.py -- not merely a check that CORSMiddleware is
importable or registered. Self-contained fixtures mirror every other
API test file's established pattern; authentication-header tests reuse
the existing auth flow to prove CORS configuration does not interfere
with it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.db.session import get_db
from app.main import app
from app.models import Base
from app.seed.seed import seed_reference_data

_ALLOWED_ORIGIN_1 = "http://localhost:5173"
_ALLOWED_ORIGIN_2 = "http://127.0.0.1:5173"
_DISALLOWED_ORIGIN = "http://evil.example.com"


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
def api_seeded_session(api_session_factory):
    session = api_session_factory()
    seed_reference_data(session)
    session.commit()
    yield session
    session.close()


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


# --- Allowed origins -------------------------------------------------------------


def test_localhost_5173_is_an_allowed_origin(api_seeded_session, client):
    response = client.get("/spreads", headers={"Origin": _ALLOWED_ORIGIN_1})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN_1


def test_127_0_0_1_5173_is_an_allowed_origin(api_seeded_session, client):
    response = client.get("/spreads", headers={"Origin": _ALLOWED_ORIGIN_2})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN_2


# --- Disallowed origin ------------------------------------------------------------


def test_disallowed_origin_receives_no_allow_origin_header(api_seeded_session, client):
    """The request itself still completes (Starlette does not reject it
    server-side) -- CORS enforcement is a browser behavior triggered by
    the *absence* of this header, not a server-side block. Asserting
    the header's absence is the correct, direct proof.
    """
    response = client.get("/spreads", headers={"Origin": _DISALLOWED_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


# --- Preflight ----------------------------------------------------------------


def test_preflight_for_an_allowed_origin_and_method_succeeds(api_seeded_session, client):
    response = client.options(
        "/spreads",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN_1


def test_preflight_for_a_post_route_with_authorization_and_content_type_succeeds(api_seeded_session, client):
    response = client.options(
        "/readings",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_preflight_for_a_disallowed_origin_does_not_grant_access(api_seeded_session, client):
    response = client.options(
        "/spreads",
        headers={
            "Origin": _DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


# --- Allowed methods ----------------------------------------------------------


def test_allowed_methods_are_exactly_get_and_post(api_seeded_session, client):
    response = client.options(
        "/spreads",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "GET",
        },
    )

    allowed_methods = {m.strip() for m in response.headers["access-control-allow-methods"].split(",")}
    assert allowed_methods == {"GET", "POST"}


def test_delete_is_not_an_allowed_method(api_seeded_session, client):
    response = client.options(
        "/spreads",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "DELETE",
        },
    )

    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" not in allowed_methods


# --- Allowed headers ------------------------------------------------------------


def test_authorization_header_is_explicitly_allowed(api_seeded_session, client):
    response = client.options(
        "/readings",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_content_type_header_is_explicitly_allowed(api_seeded_session, client):
    response = client.options(
        "/readings",
        headers={
            "Origin": _ALLOWED_ORIGIN_1,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert "content-type" in response.headers["access-control-allow-headers"].lower()


# --- Credentials ----------------------------------------------------------------


def test_credentials_are_not_enabled(api_seeded_session, client):
    """allow_credentials=False -- this API uses Authorization-header
    JWTs, never cookies, so browser credential mode is never needed
    (Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 3).
    """
    response = client.get("/spreads", headers={"Origin": _ALLOWED_ORIGIN_1})

    assert "access-control-allow-credentials" not in response.headers


# --- Existing authenticated requests remain unaffected -------------------------


def test_authenticated_request_with_authorization_header_still_works_cross_origin(
    api_seeded_session, client
):
    register = client.post(
        "/auth/register",
        json={"email": "cors@example.com", "password": "correct horse battery staple"},
        headers={"Origin": _ALLOWED_ORIGIN_1},
    )
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": "cors@example.com", "password": "correct horse battery staple"},
        headers={"Origin": _ALLOWED_ORIGIN_1},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.get(
        "/readings",
        headers={"Origin": _ALLOWED_ORIGIN_1, "Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN_1
