"""API tests for the Journal resource
(POST/GET /readings/{reading_id}/journal-entries). Self-contained
fixtures, mirroring tests/test_api_scripture.py's own established
pattern exactly.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Base, User
from app.models.reading import Reading
from app.seed.seed import seed_reference_data
from tests.factories import make_user
from tests.interpretation_helpers import build_reading


def _thin_reading(session: Session, owner: User) -> Reading:
    from app.models import Orientation

    return build_reading(
        session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)], owner=owner,
    )


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
def owner(api_seeded_session) -> User:
    user = make_user(api_seeded_session, email="owner@example.com")
    api_seeded_session.commit()
    return user


@pytest.fixture()
def auth_headers(owner) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(owner.id)}"}


@pytest.fixture()
def client(api_session_factory, auth_headers):
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
        test_client.headers.update(auth_headers)
        yield test_client
    app.dependency_overrides.clear()


# --- Creation ------------------------------------------------------------------


def test_create_journal_entry_returns_201(api_seeded_session, client, owner):
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/journal-entries", json={"content": "A first reflection."})

    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "A first reflection."
    assert body["reading_id"] == str(reading.id)


def test_journal_entries_do_not_require_interpretation(api_seeded_session, client, owner):
    """Journaling must remain usable on a Reading that has never been
    interpreted -- it is entirely independent of the
    Interpretation/Narrative/Scripture/AI pipeline.
    """
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/journal-entries", json={"content": "No interpretation yet."})

    assert response.status_code == 201


def test_blank_content_is_rejected_with_422(api_seeded_session, client, owner):
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/journal-entries", json={"content": "   "})

    assert response.status_code == 422


# --- Listing ---------------------------------------------------------------------


def test_list_journal_entries_returns_empty_list_when_none_exist(api_seeded_session, client, owner):
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/journal-entries")

    assert response.status_code == 200
    assert response.json() == []


def test_list_journal_entries_returns_them_oldest_first(api_seeded_session, client, owner):
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/journal-entries", json={"content": "First."})
    client.post(f"/readings/{reading.id}/journal-entries", json={"content": "Second."})

    response = client.get(f"/readings/{reading.id}/journal-entries")

    assert [entry["content"] for entry in response.json()] == ["First.", "Second."]


def test_saving_and_reopening_a_reading_preserves_journal_entries(api_seeded_session, client, owner):
    """Simulates "save and reopen a reading" (writing an entry, then
    fetching it again as a fresh GET would on page reload).
    """
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/journal-entries", json={"content": "Written before saving."})
    client.post(f"/readings/{reading.id}/save")

    reopened = client.get(f"/readings/{reading.id}/journal-entries")

    assert reopened.status_code == 200
    assert reopened.json()[0]["content"] == "Written before saving."


# --- Ownership / authentication ---------------------------------------------------


def test_create_journal_entry_requires_authentication(api_seeded_session, client, owner):
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post(
            f"/readings/{reading.id}/journal-entries", json={"content": "Should not work."}
        )

    assert response.status_code == 401


def test_journal_entries_are_not_visible_to_other_users(api_seeded_session, client, owner):
    other = make_user(api_seeded_session, email="other@example.com")
    api_seeded_session.commit()
    reading = _thin_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/journal-entries", json={"content": "Private to owner."})

    response = client.get(
        f"/readings/{reading.id}/journal-entries",
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )

    assert response.status_code == 404


def test_journal_entry_route_nonexistent_reading_returns_404(client):
    response = client.post(f"/readings/{uuid.uuid4()}/journal-entries", json={"content": "Anything."})

    assert response.status_code == 404
