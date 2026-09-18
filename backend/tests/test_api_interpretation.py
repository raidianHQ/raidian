"""API tests for the Interpretation API (Step 11,
Documentation/INTERPRETATION_API_DESIGN.md).

Fixtures here are deliberately self-contained (not reused from conftest.py)
because a `client` fixture needs a `get_db` override bound to a
StaticPool-backed in-memory SQLite engine shared by every request the
TestClient makes during a test -- distinct from conftest.py's `db_session`,
which hands a single already-open Session directly to test code with no
HTTP layer involved.

Step 22: every route here now requires authentication and Reading
ownership (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
Section 6/9). The `client` fixture authenticates as a single, fixed
`owner` User by default (its token is attached to every request via
`client.headers`), and every Reading this file builds is attached to that
same owner -- preserving every pre-Step-22 test's original assertions and
intent unchanged. Cross-user/unauthenticated authorization behavior is
covered separately, in tests/test_ownership.py.
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
from app.models import Base, Orientation, ReadingStatus, User
from app.models.reading import Reading
from app.seed.seed import seed_reference_data
from tests.factories import make_user
from tests.interpretation_helpers import build_reading

_FULL_CELTIC_CROSS_DRAWS = [
    ("Situation", "Ace of Swords", Orientation.UPRIGHT),
    ("Challenge", "The Tower", Orientation.UPRIGHT),
    ("Foundation", "The Hermit", Orientation.UPRIGHT),
    ("Recent Past", "The Fool", Orientation.UPRIGHT),
    ("Crown", "The Star", Orientation.UPRIGHT),
    ("Near Future", "The Moon", Orientation.UPRIGHT),
    ("Approach", "The Chariot", Orientation.UPRIGHT),
    ("External Influences", "The Empress", Orientation.UPRIGHT),
    ("Advice", "The High Priestess", Orientation.UPRIGHT),
    ("Outcome", "Strength", Orientation.UPRIGHT),
]


def _complete_reading(session: Session, owner: User) -> Reading:
    return build_reading(session, spread_name="Celtic Cross", draws=_FULL_CELTIC_CROSS_DRAWS, owner=owner)


def _incomplete_reading(session: Session, owner: User) -> Reading:
    return build_reading(
        session,
        spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Challenge", "The Tower", Orientation.UPRIGHT),
        ],
        owner=owner,
    )


# --- Fixtures ------------------------------------------------------------------


@pytest.fixture()
def api_engine():
    """A fresh, isolated in-memory SQLite database per test -- StaticPool
    keeps a single underlying connection alive for the whole test, so data
    committed via `api_seeded_session` is visible to every independent
    per-request Session the `client` fixture's get_db override creates
    (mirrors production: a shared engine, request-scoped sessions).
    """
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
    """The single User every Reading in this file is owned by (Step 22) --
    kept as a dedicated fixture so tests can still assert on its `.id`
    where needed, distinct from the client's own authentication.
    """
    user = make_user(api_seeded_session, email="owner@example.com")
    api_seeded_session.commit()
    return user


@pytest.fixture()
def auth_headers(owner) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(owner.id)}"}


@pytest.fixture()
def client(api_session_factory, auth_headers):
    """A TestClient whose get_db dependency is overridden to use the same
    engine api_seeded_session is built against -- reproduces production's
    real commit-on-success/rollback-on-exception get_db() (app/db/session.py)
    against a fresh Session per request, instead of the production
    SessionLocal/engine bound to the configured DATABASE_URL.

    Authenticates as `owner` by default (Step 22) -- every existing call
    site below (none of which passes its own `headers=`) is therefore
    automatically authorized against Readings built via `owner`.
    """

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


# --- POST /readings/{id}/interpret ----------------------------------------------


def test_post_interpret_returns_201_for_a_complete_reading(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")

    assert response.status_code == 201
    body = response.json()
    assert body["reading_id"] == str(reading.id)
    assert body["sequence"] == 1
    assert "interpretive_model" in body
    assert body["interpretive_model"]["central_issue"]["value"]


def test_post_interpret_returns_404_for_a_nonexistent_reading(client):
    response = client.post(f"/readings/{uuid.uuid4()}/interpret")
    assert response.status_code == 404


def test_post_interpret_returns_409_for_an_incomplete_reading(api_seeded_session, client, owner):
    reading = _incomplete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.DRAFTING
    assert reloaded.interpretations == []


def test_repeated_interpretation_creates_history(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    first = client.post(f"/readings/{reading.id}/interpret")
    second = client.post(f"/readings/{reading.id}/interpret")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["sequence"] < second.json()["sequence"]


def test_saved_reading_remains_saved_after_interpretation(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    reading.status = ReadingStatus.SAVED
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")

    assert response.status_code == 201
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.SAVED  # never regressed


# --- GET /readings/{id}/interpretations/current ---------------------------------


def test_get_current_interpretation_returns_200(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/interpretations/current")

    assert response.status_code == 200
    assert response.json()["reading_id"] == str(reading.id)


def test_get_current_interpretation_returns_404_when_never_interpreted(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/interpretations/current")

    assert response.status_code == 404


def test_get_current_interpretation_returns_404_for_a_nonexistent_reading(client):
    response = client.get(f"/readings/{uuid.uuid4()}/interpretations/current")
    assert response.status_code == 404


def test_get_current_interpretation_is_the_highest_sequence(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    second = client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/interpretations/current")

    assert response.status_code == 200
    assert response.json()["id"] == second.json()["id"]


# --- GET /readings/{id}/interpretations (history) --------------------------------


def test_get_history_returns_200_with_empty_list_when_never_interpreted(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/interpretations")

    assert response.status_code == 200
    assert response.json() == []


def test_get_history_returns_404_for_a_nonexistent_reading(client):
    response = client.get(f"/readings/{uuid.uuid4()}/interpretations")
    assert response.status_code == 404


def test_get_history_returns_lightweight_entries_newest_first(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    first = client.post(f"/readings/{reading.id}/interpret").json()
    second = client.post(f"/readings/{reading.id}/interpret").json()

    response = client.get(f"/readings/{reading.id}/interpretations")

    assert response.status_code == 200
    body = response.json()
    assert [entry["id"] for entry in body] == [second["id"], first["id"]]
    assert "interpretive_model" not in body[0]  # lightweight, not the full model


# --- GET /readings/{id}/narrative -------------------------------------------------


def test_get_narrative_returns_200(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/narrative")

    assert response.status_code == 200
    body = response.json()
    assert body["sections"]
    assert any(section["id"] == "central_theme" for section in body["sections"])


def test_get_narrative_returns_404_when_never_interpreted(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/narrative")

    assert response.status_code == 404


def test_get_narrative_returns_404_for_a_nonexistent_reading(client):
    response = client.get(f"/readings/{uuid.uuid4()}/narrative")
    assert response.status_code == 404


def test_get_narrative_is_generated_on_demand_not_cached(api_seeded_session, client, owner):
    """Two consecutive GETs must independently recompute the same content
    (NarrativeModel is never persisted -- INTERPRETATION_API_DESIGN.md
    Section 9) rather than one call implicitly depending on a side effect
    of the other.
    """
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    first = client.get(f"/readings/{reading.id}/narrative").json()
    second = client.get(f"/readings/{reading.id}/narrative").json()

    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


# --- API does not bypass orchestration --------------------------------------------


def test_post_interpret_calls_the_orchestration_layer(api_seeded_session, client, owner, monkeypatch):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    calls = []
    real = api_module.interpret_reading

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "interpret_reading", _spy)

    response = client.post(f"/readings/{reading.id}/interpret")

    assert response.status_code == 201
    assert calls == [reading.id]


def test_get_current_calls_the_orchestration_layer(api_seeded_session, client, owner, monkeypatch):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    calls = []
    real = api_module.get_current_interpretation

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "get_current_interpretation", _spy)

    response = client.get(f"/readings/{reading.id}/interpretations/current")

    assert response.status_code == 200
    assert calls == [reading.id]


def test_get_history_calls_the_orchestration_layer(api_seeded_session, client, owner, monkeypatch):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    calls = []
    real = api_module.list_interpretations

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "list_interpretations", _spy)

    response = client.get(f"/readings/{reading.id}/interpretations")

    assert response.status_code == 200
    assert calls == [reading.id]


def test_get_narrative_calls_the_orchestration_layer(api_seeded_session, client, owner, monkeypatch):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    calls = []
    real = api_module.get_narrative_for_reading

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(api_module, "get_narrative_for_reading", _spy)

    response = client.get(f"/readings/{reading.id}/narrative")

    assert response.status_code == 200
    assert calls == [reading.id]


# --- Provenance / reference-data version survive API serialization ---------------


def test_provenance_survives_api_serialization(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")
    body = response.json()

    real_draw_ids = {str(draw.id) for draw in reading.card_draws}
    central_issue_citations = body["interpretive_model"]["central_issue"]["citations"]
    assert central_issue_citations
    for citation in central_issue_citations:
        if citation["source_type"] == "card_draw":
            assert citation["card_draw_id"] in real_draw_ids


def test_reference_data_version_survives_api_serialization(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    post_body = client.post(f"/readings/{reading.id}/interpret").json()
    current_body = client.get(f"/readings/{reading.id}/interpretations/current").json()
    narrative_body = client.get(f"/readings/{reading.id}/narrative").json()

    reference_data_version = post_body["reference_data_version"]
    assert len(reference_data_version) == 64  # sha256 hex digest
    assert post_body["interpretive_model"]["reference_data_version"] == reference_data_version
    assert current_body["reference_data_version"] == reference_data_version
    assert narrative_body["source_reference_data_version"] == reference_data_version


# --- OpenAPI route registration ---------------------------------------------------


def test_all_four_routes_are_registered_in_the_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "post" in paths["/readings/{reading_id}/interpret"]
    assert "get" in paths["/readings/{reading_id}/interpretations/current"]
    assert "get" in paths["/readings/{reading_id}/interpretations"]
    assert "get" in paths["/readings/{reading_id}/narrative"]
