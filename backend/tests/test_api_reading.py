"""API tests for the Reading resource: Reading creation (Step 27), Save
Reading, and Reading History (Step 24,
Documentation/READING_CREATION_API_DESIGN.md,
Documentation/SAVE_READING_DESIGN.md,
Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md).

Self-contained fixtures, mirroring tests/test_ownership.py's established
pattern -- no default Authorization header on `client`, since several
tests here need to control which of two distinct users is authenticated.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.reading as reading_api_module
import app.services.reading_orchestration as orchestration_module
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import (
    Base,
    CardDraw,
    Deck,
    Interpretation,
    Orientation,
    ReadingStatus,
    ReflectionSession,
    Spread,
    User,
)
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


def _complete_reading(session: Session, owner: User) -> Reading:
    reading = build_reading(session, spread_name="Three Card", draws=_THREE_CARD_DRAWS, owner=owner)
    session.commit()
    return reading


def _drafting_reading(session: Session, owner: User) -> Reading:
    reading = build_reading(
        session,
        spread_name="Three Card",
        draws=[("Recent Past", "The Fool", Orientation.UPRIGHT)],
        owner=owner,
    )
    session.commit()
    return reading


# =====================================================================================
# Save Reading -- POST /readings/{reading_id}/save
# =====================================================================================


def test_owner_can_save_a_spread_complete_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner1@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(reading.id)
    assert body["status"] == "saved"


def test_owner_can_save_an_interpreted_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner2@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "saved"


def test_saving_an_already_saved_reading_is_idempotent(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner3@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    first = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    second = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "saved"


def test_saving_a_drafting_reading_is_rejected_with_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner4@example.com")
    api_seeded_session.commit()
    reading = _drafting_reading(api_seeded_session, owner)
    assert reading.status == ReadingStatus.DRAFTING

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.DRAFTING  # unchanged


def test_cross_user_save_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner5@example.com")
    other = make_user(api_seeded_session, email="other5@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(other))

    assert response.status_code == 404
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.SPREAD_COMPLETE  # unchanged


def test_unauthenticated_save_returns_401(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner6@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/save")

    assert response.status_code == 401


def test_save_of_a_nonexistent_reading_returns_404(api_seeded_session, client):
    user = make_user(api_seeded_session, email="owner7@example.com")
    api_seeded_session.commit()

    response = client.post(f"/readings/{uuid.uuid4()}/save", headers=_auth_header(user))

    assert response.status_code == 404


def test_save_of_an_unowned_reading_fails_closed(api_seeded_session, client):
    """A Reading whose ReflectionSession.owner_id is None (Step 22's
    "fail closed" guarantee, re-verified here for this new route
    specifically) must be inaccessible to every authenticated user, not
    just non-owners.
    """
    user = make_user(api_seeded_session, email="owner8@example.com")
    api_seeded_session.commit()
    unowned_reading = build_reading(api_seeded_session, spread_name="Three Card", draws=_THREE_CARD_DRAWS)
    api_seeded_session.commit()
    assert unowned_reading.reflection_session.owner_id is None

    response = client.post(f"/readings/{unowned_reading.id}/save", headers=_auth_header(user))

    assert response.status_code == 404


def test_save_does_not_create_interpretation_rows(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner9@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    api_seeded_session.expire_all()
    count_before = api_seeded_session.execute(
        select(Interpretation).where(Interpretation.reading_id == reading.id)
    ).all()

    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    api_seeded_session.expire_all()
    count_after = api_seeded_session.execute(
        select(Interpretation).where(Interpretation.reading_id == reading.id)
    ).all()
    assert len(count_after) == len(count_before)


def test_save_does_not_invoke_narrative_generation(api_seeded_session, client, monkeypatch):
    """Proves saving triggers no narrative-assembly side effect -- Narrative
    itself is never persisted anywhere in this schema (no table exists for
    it), so the meaningful proof is that mark_saved() never even calls
    into the Narrative Layer, not merely that no row appears.
    """
    owner = make_user(api_seeded_session, email="owner10@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))

    calls = []
    real = orchestration_module.assemble_narrative

    def _spy(model):
        calls.append(model)
        return real(model)

    monkeypatch.setattr(orchestration_module, "assemble_narrative", _spy)

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    assert response.status_code == 200
    assert calls == []


def test_save_does_not_alter_card_draws(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner11@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    before = [
        (d.id, d.position_id, d.card_id, d.orientation, d.draw_order)
        for d in api_seeded_session.execute(
            select(CardDraw).where(CardDraw.reading_id == reading.id)
        ).scalars()
    ]

    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    api_seeded_session.expire_all()
    after = [
        (d.id, d.position_id, d.card_id, d.orientation, d.draw_order)
        for d in api_seeded_session.execute(
            select(CardDraw).where(CardDraw.reading_id == reading.id)
        ).scalars()
    ]
    assert sorted(after) == sorted(before)


def test_save_commits_through_the_api_boundary(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="owner12@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    assert response.status_code == 200

    # A completely fresh session/connection-level read (not the same
    # in-process object) confirms the write was actually committed, not
    # merely visible in-memory to whichever session handled the request.
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.SAVED


# =====================================================================================
# Reading History -- GET /readings
# =====================================================================================


def test_owner_sees_their_saved_readings(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="hist1@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get("/readings", headers=_auth_header(owner))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(reading.id)


def test_unsaved_readings_are_excluded_from_history(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="hist2@example.com")
    api_seeded_session.commit()
    _complete_reading(api_seeded_session, owner)  # SPREAD_COMPLETE, never saved

    response = client.get("/readings", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json() == []


def test_another_users_saved_readings_are_excluded(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="hist3@example.com")
    other = make_user(api_seeded_session, email="hist3other@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get("/readings", headers=_auth_header(other))

    assert response.status_code == 200
    assert response.json() == []


def test_unowned_saved_readings_are_excluded_from_everyones_history(api_seeded_session, client):
    user = make_user(api_seeded_session, email="hist4@example.com")
    api_seeded_session.commit()
    unowned = build_reading(api_seeded_session, spread_name="Three Card", draws=_THREE_CARD_DRAWS)
    unowned.mark_saved()
    api_seeded_session.commit()

    response = client.get("/readings", headers=_auth_header(user))

    assert response.status_code == 200
    assert response.json() == []


def test_history_is_ordered_newest_first_by_updated_at(api_seeded_session, client):
    """Constructs an unambiguous before/after updated_at directly (rather
    than relying on real wall-clock deltas between two API calls) because
    SQLite's CURRENT_TIMESTAMP is only second-granular -- the same class
    of tie-break risk this project already solved for Interpretation.sequence
    vs. created_at (READING_INTEGRATION_DESIGN.md Section 7, Resolved Q2).
    Does not change the approved ordering rule (updated_at DESC) or
    introduce a new field -- purely a deterministic test-construction
    technique.
    """
    owner = make_user(api_seeded_session, email="hist5@example.com")
    api_seeded_session.commit()
    older = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{older.id}/save", headers=_auth_header(owner))

    newer = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{newer.id}/save", headers=_auth_header(owner))

    api_seeded_session.expire_all()
    older_row = api_seeded_session.get(Reading, older.id)
    newer_row = api_seeded_session.get(Reading, newer.id)
    now = datetime.now(timezone.utc)
    older_row.updated_at = now - timedelta(minutes=5)
    newer_row.updated_at = now
    api_seeded_session.commit()

    response = client.get("/readings", headers=_auth_header(owner))

    assert response.status_code == 200
    ids = [entry["id"] for entry in response.json()]
    assert ids == [str(newer.id), str(older.id)]


def test_empty_history_returns_200_with_empty_list(api_seeded_session, client):
    user = make_user(api_seeded_session, email="hist6@example.com")
    api_seeded_session.commit()

    response = client.get("/readings", headers=_auth_header(user))

    assert response.status_code == 200
    assert response.json() == []


def test_a_reading_appears_exactly_once_even_with_multiple_interpretations(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="hist7@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get("/readings", headers=_auth_header(owner))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(reading.id)


def test_history_entries_do_not_embed_interpretation_content(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="hist8@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get("/readings", headers=_auth_header(owner))

    entry = response.json()[0]
    assert "interpretive_model" not in entry
    assert "interpretations" not in entry
    assert set(entry.keys()) == {"id", "status", "question", "question_domain", "created_at", "updated_at"}


def test_unauthenticated_history_request_returns_401(client):
    response = client.get("/readings")
    assert response.status_code == 401


# =====================================================================================
# Reading Creation -- POST /readings (Step 27, Documentation/READING_CREATION_API_DESIGN.md)
# =====================================================================================


def _seeded_spread(session: Session, name: str = "Three Card") -> Spread:
    return session.scalars(select(Spread).where(Spread.name == name)).one()


def _default_deck(session: Session) -> Deck:
    return session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()


def _create_payload(session: Session, **overrides) -> dict:
    payload = {
        "spread_id": str(_seeded_spread(session).id),
        "question": "What should I focus on right now?",
    }
    payload.update(overrides)
    return payload


def test_authenticated_user_can_create_a_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create1@example.com")
    api_seeded_session.commit()

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "drafting"
    assert body["question"] == "What should I focus on right now?"
    assert set(body.keys()) == {"id", "status", "question", "question_domain", "created_at", "updated_at"}


def test_unauthenticated_creation_returns_401(api_seeded_session, client):
    response = client.post("/readings", json=_create_payload(api_seeded_session))
    assert response.status_code == 401


def test_creation_with_nonexistent_spread_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create2@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json={"spread_id": str(uuid.uuid4()), "question": "What now?"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_creation_with_nonexistent_deck_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create3@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json=_create_payload(api_seeded_session, deck_id=str(uuid.uuid4())),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_creation_with_blank_question_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create4@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings", json=_create_payload(api_seeded_session, question=""), headers=_auth_header(owner)
    )

    assert response.status_code == 422


def test_creation_with_whitespace_only_question_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create5@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings", json=_create_payload(api_seeded_session, question="   "), headers=_auth_header(owner)
    )

    assert response.status_code == 422


def test_creation_with_question_over_4000_characters_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create6@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json=_create_payload(api_seeded_session, question="a" * 4001),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_creation_with_question_at_exactly_4000_characters_succeeds(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create7@example.com")
    api_seeded_session.commit()
    question = "a" * 4000

    response = client.post(
        "/readings", json=_create_payload(api_seeded_session, question=question), headers=_auth_header(owner)
    )

    assert response.status_code == 201
    assert response.json()["question"] == question


def test_creation_with_question_domain_over_60_characters_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create8@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json=_create_payload(api_seeded_session, question_domain="a" * 61),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_creation_with_question_domain_at_exactly_60_characters_succeeds(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create9@example.com")
    api_seeded_session.commit()
    domain = "a" * 60

    response = client.post(
        "/readings",
        json=_create_payload(api_seeded_session, question_domain=domain),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["question_domain"] == domain


def test_creation_with_malformed_spread_id_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create10@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json={"spread_id": "not-a-uuid", "question": "What now?"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_creation_request_with_extraneous_owner_field_is_rejected(api_seeded_session, client):
    """ReadingCreateRequest has no owner/user field at all, and its shared
    _Model base forbids unrecognized fields outright (extra="forbid") --
    a client attempting to smuggle in an owner_id is rejected as a
    malformed request, never silently accepted or used
    (Documentation/READING_CREATION_API_DESIGN.md Section 3.1/12).
    """
    owner = make_user(api_seeded_session, email="create11@example.com")
    other = make_user(api_seeded_session, email="create11other@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings",
        json=_create_payload(api_seeded_session, owner_id=str(other.id)),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(Reading)).all() == []


def test_creation_propagates_ownership_to_reflection_session(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create12@example.com")
    api_seeded_session.commit()

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))
    reading_id = uuid.UUID(response.json()["id"])

    api_seeded_session.expire_all()
    reading = api_seeded_session.get(Reading, reading_id)
    assert reading.reflection_session.owner_id == owner.id


def test_created_reading_initial_status_is_drafting(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create13@example.com")
    api_seeded_session.commit()

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))
    reading_id = uuid.UUID(response.json()["id"])

    api_seeded_session.expire_all()
    reading = api_seeded_session.get(Reading, reading_id)
    assert reading.status == ReadingStatus.DRAFTING


def test_creation_failure_after_flush_leaves_no_partial_persistence(api_seeded_session, client, monkeypatch):
    """Forces a failure *after* create_reading() has already flushed both
    the ReflectionSession and the Reading, but before the request
    completes -- proving get_db()'s single commit point (unmodified since
    Step 11) discards both rows together, since flush is not commit
    (Documentation/READING_CREATION_API_DESIGN.md Section 8).
    """
    owner = make_user(api_seeded_session, email="create14@example.com")
    api_seeded_session.commit()

    def _boom(_reading):
        raise RuntimeError("simulated post-creation failure")

    monkeypatch.setattr(reading_api_module, "_to_summary", _boom)

    with pytest.raises(RuntimeError):
        client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))

    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(Reading)).all() == []
    assert (
        api_seeded_session.execute(select(ReflectionSession).where(ReflectionSession.owner_id == owner.id)).all()
        == []
    )


def test_two_users_creating_readings_remain_independently_owned(api_seeded_session, client):
    alice = make_user(api_seeded_session, email="create15alice@example.com")
    bob = make_user(api_seeded_session, email="create15bob@example.com")
    api_seeded_session.commit()

    alice_response = client.post(
        "/readings", json=_create_payload(api_seeded_session), headers=_auth_header(alice)
    )
    bob_response = client.post(
        "/readings", json=_create_payload(api_seeded_session), headers=_auth_header(bob)
    )

    alice_reading_id = uuid.UUID(alice_response.json()["id"])
    bob_reading_id = uuid.UUID(bob_response.json()["id"])
    assert alice_reading_id != bob_reading_id

    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, alice_reading_id).reflection_session.owner_id == alice.id
    assert api_seeded_session.get(Reading, bob_reading_id).reflection_session.owner_id == bob.id

    # Cross-user access through an existing, already-owned-gated route
    # remains 404, exactly as tests/test_ownership.py already established.
    cross = client.get(f"/readings/{alice_reading_id}/interpretations", headers=_auth_header(bob))
    assert cross.status_code == 404


def test_omitted_deck_id_resolves_to_seeded_default_deck(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create16@example.com")
    api_seeded_session.commit()
    expected_deck = _default_deck(api_seeded_session)

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))
    reading_id = uuid.UUID(response.json()["id"])

    api_seeded_session.expire_all()
    reading = api_seeded_session.get(Reading, reading_id)
    assert reading.deck_id == expected_deck.id


def test_omitted_question_domain_persists_as_none(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create17@example.com")
    api_seeded_session.commit()

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))

    assert response.json()["question_domain"] is None
    api_seeded_session.expire_all()
    reading = api_seeded_session.get(Reading, uuid.UUID(response.json()["id"]))
    assert reading.question_domain is None


def test_created_reading_is_retrievable_through_existing_owned_reading_path(api_seeded_session, client):
    """Proves the new Reading is a fully real, ownable resource from the
    moment of creation -- reachable through the already-existing,
    unmodified get_owned_reading-gated routes (Step 22), not a special or
    partial one.
    """
    owner = make_user(api_seeded_session, email="create18@example.com")
    api_seeded_session.commit()

    created = client.post(
        "/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner)
    ).json()

    response = client.get(f"/readings/{created['id']}/interpretations", headers=_auth_header(owner))
    assert response.status_code == 200
    assert response.json() == []


def test_creation_creates_no_card_draw_interpretation_or_narrative_rows(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create19@example.com")
    api_seeded_session.commit()

    response = client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))
    reading_id = uuid.UUID(response.json()["id"])

    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading_id)).all() == []
    assert (
        api_seeded_session.execute(select(Interpretation).where(Interpretation.reading_id == reading_id)).all()
        == []
    )
    # NarrativeModel is never persisted anywhere in this schema (unchanged,
    # Step 6/7) -- there is no table to check.


def test_created_reading_does_not_appear_in_history_before_being_saved(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="create20@example.com")
    api_seeded_session.commit()
    client.post("/readings", json=_create_payload(api_seeded_session), headers=_auth_header(owner))

    response = client.get("/readings", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json() == []
