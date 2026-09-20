"""API tests for the optional Scriptural Reflection endpoint
(GET /readings/{reading_id}/scripture,
Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15).

Self-contained fixtures, mirroring tests/test_api_interpretation.py's own
established pattern exactly (a `client` fixture pre-authenticated as a
single `owner` User) -- this file only adds cross-user/unauthenticated
checks where they differ from that default.
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
from app.models import Base, Orientation, User
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


# --- Scripture enabled (successful fetch) -----------------------------------------


def test_scripture_route_returns_200_for_an_interpreted_reading(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/scripture")

    assert response.status_code == 200
    body = response.json()
    assert "reflections" in body
    assert "disclaimer" in body
    assert isinstance(body["reflections"], list)


def test_scripture_response_disclaims_divine_endorsement(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/scripture")

    disclaimer = response.json()["disclaimer"]
    assert "God's will" in disclaimer


def test_scripture_reflection_shape_when_a_mapping_exists(api_seeded_session, client, owner):
    """The rich Celtic Cross fixture's own real theme_strength includes
    "patience" (count 2 -- test_interpretation_engine.py's own
    test_theme_strength_entries_with_count_2_or_more_are_reinforced_themes
    confirms this fixture has real >=2-count themes), and the real seed
    data maps "patience" to James 1:2-4 -- proving the full pipeline
    (engine -> theme_strength -> ScriptureReference lookup -> API)
    connects end to end, not just at the service-test level.
    """
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/scripture")

    reflections = response.json()["reflections"]
    assert len(reflections) >= 1
    for reflection in reflections:
        assert set(reflection.keys()) == {
            "theme", "book", "chapter", "verse_start", "verse_end", "reference_display",
            "translation", "context_note", "reflection_connection", "theme_citations",
        }
        assert reflection["translation"] in ("KJV", "WEB", "ASV")
        assert len(reflection["theme_citations"]) >= 1


# --- No Scripture returned when no approved mapping exists -----------------------


def test_scripture_reflections_empty_but_200_when_no_theme_has_an_approved_mapping(
    api_seeded_session, client, owner
):
    thin_reading = build_reading(
        api_seeded_session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
        owner=owner,
    )
    api_seeded_session.commit()
    client.post(f"/readings/{thin_reading.id}/interpret")

    response = client.get(f"/readings/{thin_reading.id}/scripture")

    assert response.status_code == 200
    # Four of Wands's own themes are not among this foundation's seeded
    # Scripture themes (fear/anxiety/patience/relationships/grief/hope/
    # uncertainty) -- an empty list is the correct, non-error outcome.
    assert response.json()["reflections"] == []


# --- Scripture is optional: never triggered by, or required for, other routes ----


def test_interpret_and_narrative_never_call_the_scripture_layer(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    interpret_response = client.post(f"/readings/{reading.id}/interpret")
    narrative_response = client.get(f"/readings/{reading.id}/narrative")

    assert interpret_response.status_code == 201
    assert narrative_response.status_code == 200
    assert "reflections" not in interpret_response.json()
    assert "scripture" not in narrative_response.json()
    assert "reflections" not in narrative_response.json()


def test_scripture_never_returned_before_it_is_explicitly_requested(api_seeded_session, client, owner):
    """A Reading's interpretation is complete and correct without ever
    calling GET .../scripture -- proving "Scripture Off" requires no
    stored flag at this foundation stage, just not calling this route.
    """
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    interpret_response = client.post(f"/readings/{reading.id}/interpret")
    current_response = client.get(f"/readings/{reading.id}/interpretations/current")

    assert interpret_response.status_code == 201
    assert current_response.status_code == 200
    assert "scripture" not in current_response.json()["interpretive_model"]
    assert "reflections" not in current_response.json()["interpretive_model"]


# --- Scripture layer does not alter deterministic tarot interpretation -----------


def test_calling_scripture_does_not_change_the_persisted_interpretation(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    before = client.get(f"/readings/{reading.id}/interpretations/current").json()
    client.get(f"/readings/{reading.id}/scripture")
    after = client.get(f"/readings/{reading.id}/interpretations/current").json()

    assert before == after


def test_calling_scripture_repeatedly_does_not_create_new_interpretation_rows(
    api_seeded_session, client, owner
):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    client.get(f"/readings/{reading.id}/scripture")
    client.get(f"/readings/{reading.id}/scripture")

    history = client.get(f"/readings/{reading.id}/interpretations").json()
    assert len(history) == 1


# --- Never interpreted -----------------------------------------------------------


def test_scripture_route_returns_404_when_never_interpreted(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/scripture")

    assert response.status_code == 404


# --- Ownership / authentication ---------------------------------------------------


def test_scripture_route_requires_authentication(api_seeded_session, client, owner):
    """`client` pre-attaches an Authorization header to every request
    (this file's own fixture, mirroring test_api_interpretation.py) --
    passing `headers={}` to a single call does not remove it (httpx
    merges per-request headers on top of the client's own, it does not
    replace them), so an unauthenticated request needs its own bare
    TestClient instead. `app.dependency_overrides[get_db]` is already
    active for the duration of this test via the `client` fixture above.
    """
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get(f"/readings/{reading.id}/scripture")

    assert response.status_code == 401


def test_scripture_route_cross_user_returns_404(api_seeded_session, client, owner):
    other = make_user(api_seeded_session, email="other@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(
        f"/readings/{reading.id}/scripture",
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )

    assert response.status_code == 404


def test_scripture_route_nonexistent_reading_returns_404(client):
    response = client.get(f"/readings/{uuid.uuid4()}/scripture")

    assert response.status_code == 404
