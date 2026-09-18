"""Authentication/ownership boundary tests (Step 22,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
6/8/10).

Self-contained fixtures mirroring test_api_interpretation.py's established
pattern. Unlike that file, `client` here attaches no default Authorization
header -- every test controls headers explicitly, since the whole point of
this file is proving cross-user isolation.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.interpretation as api_module
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Base, Orientation, User
from app.models.reading import Reading
from app.seed.seed import seed_reference_data
from tests.factories import make_user
from tests.interpretation_helpers import build_reading

_THREE_CARD_DRAWS = [
    ("Recent Past", "The Fool", Orientation.UPRIGHT),
    ("Present Situation", "The Magician", Orientation.UPRIGHT),
    ("Near Future", "The Star", Orientation.UPRIGHT),
]


# --- Fixtures ------------------------------------------------------------------


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


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _reading_for(session: Session, owner: User) -> Reading:
    reading = build_reading(session, spread_name="Three Card", draws=_THREE_CARD_DRAWS, owner=owner)
    session.commit()
    return reading


# --- get_owned_reading behavior table (Step 21 Section 6.3 / Step 22 Phase 10) ------


def test_owner_can_access_their_own_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}/interpretations", headers=_auth_header(owner))
    assert response.status_code == 200


def test_a_different_user_receives_404_for_another_users_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner2@example.com")
    other = make_user(api_seeded_session, email="other2@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}/interpretations", headers=_auth_header(other))
    assert response.status_code == 404


def test_unauthenticated_request_is_rejected(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner3@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}/interpretations")
    assert response.status_code == 401


def test_nonexistent_reading_returns_404_for_an_authenticated_user(api_seeded_session, client):
    user = make_user(api_seeded_session, email="lonely@example.com")
    api_seeded_session.commit()

    response = client.get(f"/readings/{uuid.uuid4()}/interpretations", headers=_auth_header(user))
    assert response.status_code == 404


def test_nonexistent_reading_and_unowned_reading_return_identical_responses(api_seeded_session, client):
    """404, never 403, for both cases, and indistinguishable from each
    other -- Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md Section 8.4's
    resource-enumeration-resistant design.
    """
    owner = make_user(api_seeded_session, email="owner4@example.com")
    other = make_user(api_seeded_session, email="other4@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    unowned = client.get(f"/readings/{reading.id}/interpretations", headers=_auth_header(other))
    nonexistent = client.get(f"/readings/{uuid.uuid4()}/interpretations", headers=_auth_header(other))

    assert unowned.status_code == nonexistent.status_code == 404
    assert unowned.json() == nonexistent.json()


# --- All four routes, individually (Step 22 Phase 13 "Existing API routes") --------


@pytest.mark.parametrize(
    "method, path_suffix",
    [
        ("post", "/interpret"),
        ("get", "/interpretations/current"),
        ("get", "/interpretations"),
        ("get", "/narrative"),
    ],
)
def test_each_route_rejects_unauthenticated_requests(api_seeded_session, client, method, path_suffix):
    slug = path_suffix.strip("/").replace("/", "-")
    owner = make_user(api_seeded_session, email=f"owner-{slug}@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    response = getattr(client, method)(f"/readings/{reading.id}{path_suffix}")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "method, path_suffix",
    [
        ("post", "/interpret"),
        ("get", "/interpretations/current"),
        ("get", "/interpretations"),
        ("get", "/narrative"),
    ],
)
def test_each_route_rejects_a_non_owning_authenticated_user(api_seeded_session, client, method, path_suffix):
    slug = path_suffix.strip("/").replace("/", "-")
    owner = make_user(api_seeded_session, email=f"owner2-{slug}@example.com")
    other = make_user(api_seeded_session, email=f"other2-{slug}@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)
    # Interpret as the owner first, so /current, /interpretations, and
    # /narrative would have real content to (wrongly) return if the
    # ownership check had failed to block the other user.
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))

    response = getattr(client, method)(f"/readings/{reading.id}{path_suffix}", headers=_auth_header(other))
    assert response.status_code == 404


@pytest.mark.parametrize(
    "method, path_suffix, expected_status",
    [
        ("post", "/interpret", 201),
        ("get", "/interpretations", 200),
    ],
)
def test_each_route_succeeds_for_the_owner(
    api_seeded_session, client, method, path_suffix, expected_status
):
    slug = path_suffix.strip("/").replace("/", "-")
    owner = make_user(api_seeded_session, email=f"owner3-{slug}@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    response = getattr(client, method)(f"/readings/{reading.id}{path_suffix}", headers=_auth_header(owner))
    assert response.status_code == expected_status


# --- Orchestration is never invoked when ownership/authentication fails -----------


def test_orchestration_is_not_invoked_when_ownership_check_fails(api_seeded_session, client, monkeypatch):
    owner = make_user(api_seeded_session, email="owner5@example.com")
    other = make_user(api_seeded_session, email="other5@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    calls = []
    real = api_module.list_interpretations

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "list_interpretations", _spy)

    response = client.get(f"/readings/{reading.id}/interpretations", headers=_auth_header(other))

    assert response.status_code == 404
    assert calls == []


def test_orchestration_is_not_invoked_for_an_unauthenticated_request(api_seeded_session, client, monkeypatch):
    owner = make_user(api_seeded_session, email="owner6@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    calls = []
    real = api_module.get_narrative_for_reading

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "get_narrative_for_reading", _spy)

    response = client.get(f"/readings/{reading.id}/narrative")

    assert response.status_code == 401
    assert calls == []


# --- Ownership propagation through the ReflectionSession relationship -------------


def test_reading_ownership_is_recognized_through_the_reflection_session_relationship(
    api_seeded_session, client
):
    owner = make_user(api_seeded_session, email="owner7@example.com")
    api_seeded_session.commit()
    reading = _reading_for(api_seeded_session, owner)

    assert reading.reflection_session.owner_id == owner.id

    response = client.get(f"/readings/{reading.id}/interpretations", headers=_auth_header(owner))
    assert response.status_code == 200
