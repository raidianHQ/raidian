"""API tests for the Reading resource: Reading creation (Step 27), Save
Reading, Reading History (Step 24), and CardDraw recording (Step 32,
Documentation/READING_CREATION_API_DESIGN.md,
Documentation/SAVE_READING_DESIGN.md,
Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md,
Documentation/CARDDRAW_API_DESIGN.md).

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
    Card,
    CardDraw,
    Deck,
    DrawMethod,
    Interpretation,
    Orientation,
    ReadingStatus,
    ReflectionSession,
    Spread,
    SpreadPosition,
    User,
)
from app.models.reading import Reading
from app.seed.seed import seed_reference_data
from tests.factories import make_deck, make_major_card, make_spread, make_user
from tests.interpretation_helpers import build_reading, get_card, get_default_deck

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
# Delete Reading -- DELETE /readings/{reading_id} (Raidian Reading Lifecycle
# improvements: Delete Saved Reading)
# =====================================================================================


def test_owner_can_delete_a_saved_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del1@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    reading_id = reading.id

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 204
    assert response.content == b""
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading_id) is None


def test_delete_cascades_to_card_draws_and_interpretations(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del2@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    reading_id = reading.id

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading_id)).all() == []
    assert (
        api_seeded_session.execute(select(Interpretation).where(Interpretation.reading_id == reading_id)).all() == []
    )


def test_delete_cascades_to_journal_entries(api_seeded_session, client):
    from app.models.journal_entry import JournalEntry

    owner = make_user(api_seeded_session, email="del3@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(
        f"/readings/{reading.id}/journal-entries",
        json={"content": "A private reflection."},
        headers=_auth_header(owner),
    )
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    reading_id = reading.id
    api_seeded_session.expire_all()
    assert len(api_seeded_session.execute(select(JournalEntry).where(JournalEntry.reading_id == reading_id)).all()) == 1

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(JournalEntry).where(JournalEntry.reading_id == reading_id)).all() == []


def test_delete_removes_the_reflection_session_too(api_seeded_session, client):
    """No orphaned ReflectionSession should remain -- Reading carries no
    owner column of its own; ReflectionSession is the ownership anchor
    (see ReflectionSession's own docstring), so a delete that only
    removed the Reading row would leave a purposeless, ownerless row
    behind.
    """
    owner = make_user(api_seeded_session, email="del4@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    reflection_session_id = reading.reflection_session_id

    response = client.delete(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.get(ReflectionSession, reflection_session_id) is None


def test_cross_user_delete_returns_404_and_deletes_nothing(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del5@example.com")
    other = make_user(api_seeded_session, email="del5other@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.delete(f"/readings/{reading.id}", headers=_auth_header(other))

    assert response.status_code == 404
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id) is not None


def test_unauthenticated_delete_returns_401(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del6@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.delete(f"/readings/{reading.id}")

    assert response.status_code == 401
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id) is not None


def test_delete_of_a_nonexistent_reading_returns_404(api_seeded_session, client):
    user = make_user(api_seeded_session, email="del7@example.com")
    api_seeded_session.commit()

    response = client.delete(f"/readings/{uuid.uuid4()}", headers=_auth_header(user))

    assert response.status_code == 404


def test_delete_of_an_unowned_reading_fails_closed(api_seeded_session, client):
    """A Reading whose ReflectionSession.owner_id is None must be
    inaccessible to every authenticated user for deletion too -- the same
    fail-closed guarantee already re-verified for /save and /draws, now
    re-verified for this new route specifically.
    """
    user = make_user(api_seeded_session, email="del8@example.com")
    api_seeded_session.commit()
    unowned_reading = build_reading(api_seeded_session, spread_name="Three Card", draws=_THREE_CARD_DRAWS)
    api_seeded_session.commit()
    assert unowned_reading.reflection_session.owner_id is None

    response = client.delete(f"/readings/{unowned_reading.id}", headers=_auth_header(user))

    assert response.status_code == 404
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, unowned_reading.id) is not None


def test_deleting_one_reading_does_not_affect_another_owned_by_the_same_user(api_seeded_session, client):
    """Do not accidentally delete unrelated user/readings data: a second
    reading owned by the very same user, sitting alongside the one being
    deleted, must be completely untouched.
    """
    owner = make_user(api_seeded_session, email="del9@example.com")
    api_seeded_session.commit()
    keep = _complete_reading(api_seeded_session, owner)
    doomed = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{doomed.id}/save", headers=_auth_header(owner))
    keep_id = keep.id
    doomed_id = doomed.id

    response = client.delete(f"/readings/{doomed_id}", headers=_auth_header(owner))

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, keep_id) is not None
    assert api_seeded_session.get(Reading, doomed_id) is None


def test_deleting_one_users_reading_does_not_affect_another_users_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del10@example.com")
    other = make_user(api_seeded_session, email="del10other@example.com")
    api_seeded_session.commit()
    mine = _complete_reading(api_seeded_session, owner)
    theirs = _complete_reading(api_seeded_session, other)
    client.post(f"/readings/{mine.id}/save", headers=_auth_header(owner))

    response = client.delete(f"/readings/{mine.id}", headers=_auth_header(owner))

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, theirs.id) is not None


def test_deleted_reading_no_longer_appears_in_history(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del11@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    delete_response = client.delete(f"/readings/{reading.id}", headers=_auth_header(owner))
    assert delete_response.status_code == 204

    response = client.get("/readings", headers=_auth_header(owner))
    assert response.status_code == 200
    assert response.json() == []


def test_delete_of_a_drafting_reading_is_rejected_with_409(api_seeded_session, client):
    """Delete is scoped to SAVED readings only -- a DRAFTING reading a
    user no longer wants is abandoned, not deleted: it simply never gets
    saved, and never appears in Reading History regardless.
    """
    owner = make_user(api_seeded_session, email="del12@example.com")
    api_seeded_session.commit()
    reading = _drafting_reading(api_seeded_session, owner)
    reading_id = reading.id

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading_id)
    assert reloaded is not None
    assert reloaded.status == ReadingStatus.DRAFTING  # unchanged


def test_delete_of_a_spread_complete_reading_is_rejected_with_409(api_seeded_session, client):
    """Same SAVED-only gate for SPREAD_COMPLETE -- a completed-but-never-
    saved reading is not deletable either; it's simply left unsaved.
    """
    owner = make_user(api_seeded_session, email="del14@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    reading_id = reading.id
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading_id)
    assert reloaded is not None
    assert reloaded.status == ReadingStatus.SPREAD_COMPLETE  # unchanged


def test_delete_of_an_interpreted_reading_is_rejected_with_409(api_seeded_session, client):
    """Same SAVED-only gate for INTERPRETED -- interpreting a reading
    does not make it deletable; only saving it does.
    """
    owner = make_user(api_seeded_session, email="del15@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    reading_id = reading.id
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading_id).status == ReadingStatus.INTERPRETED

    response = client.delete(f"/readings/{reading_id}", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading_id)
    assert reloaded is not None
    assert reloaded.status == ReadingStatus.INTERPRETED  # unchanged


def test_malformed_reading_id_on_delete_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="del13@example.com")
    api_seeded_session.commit()

    response = client.delete("/readings/not-a-uuid", headers=_auth_header(owner))

    assert response.status_code == 422


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


# =====================================================================================
# CardDraw recording -- POST /readings/{reading_id}/draws (Step 32,
# Documentation/CARDDRAW_API_DESIGN.md)
# =====================================================================================


def _empty_reading(session: Session, owner: User | None = None) -> Reading:
    """A DRAFTING "Three Card" Reading with zero CardDraw rows -- the
    starting point for every positive-path draw test.
    """
    reading = build_reading(session, spread_name="Three Card", draws=[], owner=owner)
    session.commit()
    return reading


def _spread_position(session: Session, position_name: str, spread_name: str = "Three Card") -> SpreadPosition:
    spread = _seeded_spread(session, spread_name)
    return next(p for p in spread.positions if p.name == position_name)


def _draw_payload(
    session: Session,
    position_name: str = "Recent Past",
    card_name: str = "The Fool",
    **overrides,
) -> dict:
    position = _spread_position(session, position_name)
    card = get_card(session, get_default_deck(session), card_name)
    payload = {
        "position_id": str(position.id),
        "card_id": str(card.id),
        "orientation": "upright",
    }
    payload.update(overrides)
    return payload


def test_authenticated_valid_draw_returns_201(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw1@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201


def test_unauthenticated_draw_returns_401(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw2@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws", json=_draw_payload(api_seeded_session))

    assert response.status_code == 401


def test_draw_against_nonexistent_reading_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw3@example.com")
    api_seeded_session.commit()

    response = client.post(
        f"/readings/{uuid.uuid4()}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_cross_user_draw_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw4@example.com")
    other = make_user(api_seeded_session, email="draw4other@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(other),
    )

    assert response.status_code == 404
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []


def test_draw_against_unowned_reading_fails_closed(api_seeded_session, client):
    """A Reading whose ReflectionSession.owner_id is None must be
    inaccessible to every authenticated user for drawing too -- the same
    fail-closed guarantee already re-verified for /save
    (test_save_of_an_unowned_reading_fails_closed), now re-verified for
    this new route specifically.
    """
    user = make_user(api_seeded_session, email="draw5@example.com")
    api_seeded_session.commit()
    unowned_reading = _empty_reading(api_seeded_session)
    assert unowned_reading.reflection_session.owner_id is None

    response = client.post(
        f"/readings/{unowned_reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(user),
    )

    assert response.status_code == 404


def test_successful_draw_is_persisted_with_correct_associations(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw6@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    position = _spread_position(api_seeded_session, "Recent Past")
    card = get_card(api_seeded_session, get_default_deck(api_seeded_session), "The Fool")

    response = client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(position.id), "card_id": str(card.id), "orientation": "upright"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["position_id"] == str(position.id)
    assert body["card_id"] == str(card.id)

    api_seeded_session.expire_all()
    draw = api_seeded_session.get(CardDraw, uuid.UUID(body["id"]))
    assert draw is not None
    assert draw.reading_id == reading.id
    assert draw.position_id == position.id
    assert draw.card_id == card.id


def test_upright_orientation_persists(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw7@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, orientation="upright"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["orientation"] == "upright"


def test_reversed_orientation_persists(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw8@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, orientation="reversed"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["orientation"] == "reversed"


def test_first_draw_order_is_server_computed_as_one(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw9@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.json()["draw_order"] == 1


def test_subsequent_draw_order_increments(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw10@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Present Situation", card_name="The Magician"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["draw_order"] == 2


def test_client_supplied_draw_order_is_rejected(api_seeded_session, client):
    """CardDrawCreateRequest has no draw_order field at all, and its
    shared _Model base forbids unrecognized fields outright
    (extra="forbid") -- a client attempting to supply one is rejected as
    a malformed request, never silently accepted or used
    (Documentation/CARDDRAW_API_DESIGN.md Section 4.1/4.3).
    """
    owner = make_user(api_seeded_session, email="draw11@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, draw_order=5),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []


def test_client_supplied_owner_id_is_rejected(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw12@example.com")
    other = make_user(api_seeded_session, email="draw12other@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, owner_id=str(other.id)),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_duplicate_card_is_rejected_with_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw13@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    deck = get_default_deck(api_seeded_session)
    card = get_card(api_seeded_session, deck, "The Fool")
    pos1 = _spread_position(api_seeded_session, "Recent Past")
    pos2 = _spread_position(api_seeded_session, "Present Situation")

    first = client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(pos1.id), "card_id": str(card.id), "orientation": "upright"},
        headers=_auth_header(owner),
    )
    assert first.status_code == 201

    second = client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(pos2.id), "card_id": str(card.id), "orientation": "reversed"},
        headers=_auth_header(owner),
    )

    assert second.status_code == 409
    api_seeded_session.expire_all()
    draws = api_seeded_session.execute(
        select(CardDraw).where(CardDraw.reading_id == reading.id, CardDraw.position_id == pos2.id)
    ).all()
    assert draws == []


def test_redrawing_an_already_filled_position_is_rejected_with_409(api_seeded_session, client):
    """Isolates PositionAlreadyDrawnError from DuplicateCardError by using
    two different cards -- the Reading remains DRAFTING throughout (only
    1 of 3 required positions is ever filled), so this exercises the
    in-memory pre-check (Documentation/CARDDRAW_API_DESIGN.md Section
    3.3/6), not the DRAFTING guard.
    """
    owner = make_user(api_seeded_session, email="draw14@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    position = _spread_position(api_seeded_session, "Recent Past")
    deck = get_default_deck(api_seeded_session)
    fool = get_card(api_seeded_session, deck, "The Fool")
    magician = get_card(api_seeded_session, deck, "The Magician")

    first = client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(position.id), "card_id": str(fool.id), "orientation": "upright"},
        headers=_auth_header(owner),
    )
    assert first.status_code == 201

    second = client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(position.id), "card_id": str(magician.id), "orientation": "reversed"},
        headers=_auth_header(owner),
    )

    assert second.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.DRAFTING
    draws = api_seeded_session.execute(
        select(CardDraw).where(CardDraw.reading_id == reading.id, CardDraw.position_id == position.id)
    ).scalars().all()
    assert len(draws) == 1
    assert draws[0].card_id == fool.id


def test_draw_against_a_non_drafting_reading_returns_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw15@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Star"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 409


def test_incomplete_spread_remains_drafting_after_a_draw(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw16@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["reading_status"] == "drafting"
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.DRAFTING


def test_final_required_draw_transitions_to_spread_complete(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw17@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    deck = get_default_deck(api_seeded_session)

    client.post(
        f"/readings/{reading.id}/draws",
        json={
            "position_id": str(_spread_position(api_seeded_session, "Recent Past").id),
            "card_id": str(get_card(api_seeded_session, deck, "The Fool").id),
            "orientation": "upright",
        },
        headers=_auth_header(owner),
    )
    client.post(
        f"/readings/{reading.id}/draws",
        json={
            "position_id": str(_spread_position(api_seeded_session, "Present Situation").id),
            "card_id": str(get_card(api_seeded_session, deck, "The Magician").id),
            "orientation": "upright",
        },
        headers=_auth_header(owner),
    )
    final = client.post(
        f"/readings/{reading.id}/draws",
        json={
            "position_id": str(_spread_position(api_seeded_session, "Near Future").id),
            "card_id": str(get_card(api_seeded_session, deck, "The Star").id),
            "orientation": "upright",
        },
        headers=_auth_header(owner),
    )

    assert final.status_code == 201
    assert final.json()["reading_status"] == "spread_complete"
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.SPREAD_COMPLETE


def test_completion_occurs_exactly_once(api_seeded_session, client):
    """A fourth draw attempt against an already-SPREAD_COMPLETE Three Card
    Reading (every position already filled) must be rejected, not
    silently accepted or re-triggering the transition.
    """
    owner = make_user(api_seeded_session, email="draw18@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Star"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 409
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.SPREAD_COMPLETE


def test_nonexistent_position_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw19@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_id=str(uuid.uuid4())),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_position_belonging_to_another_spread_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw20@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    foreign_position = _spread_position(api_seeded_session, "The Card", spread_name="Single Card")

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_id=str(foreign_position.id)),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_nonexistent_card_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw21@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, card_id=str(uuid.uuid4())),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_card_belonging_to_another_deck_returns_404(api_seeded_session, client):
    """The collapsing rule Documentation/CARDDRAW_API_DESIGN.md Section 6
    applies symmetrically to card_id: a Card that exists but belongs to a
    different Deck than this Reading's is treated identically to a
    nonexistent card_id.
    """
    owner = make_user(api_seeded_session, email="draw22@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    other_deck = make_deck(api_seeded_session, name="Other Deck", is_default=False)
    foreign_card = make_major_card(api_seeded_session, other_deck, name="Foreign Card")
    api_seeded_session.commit()

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, card_id=str(foreign_card.id)),
        headers=_auth_header(owner),
    )

    assert response.status_code == 404


def test_malformed_reading_id_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw23@example.com")
    api_seeded_session.commit()

    response = client.post(
        "/readings/not-a-uuid/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_malformed_position_id_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw24@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_id="not-a-uuid"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_missing_required_fields_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw25@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws", json={}, headers=_auth_header(owner))

    assert response.status_code == 422


def test_unknown_request_field_is_rejected(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw26@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, unexpected_field="surprise"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_invalid_orientation_value_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw27@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, orientation="sideways"),
        headers=_auth_header(owner),
    )

    assert response.status_code == 422


def test_transaction_rollback_on_forced_post_flush_failure(api_seeded_session, client, monkeypatch):
    """Mirrors test_creation_failure_after_flush_leaves_no_partial_persistence:
    forces a failure after record_card_draw() has already flushed the new
    CardDraw row, proving get_db()'s single commit point discards it.
    """
    owner = make_user(api_seeded_session, email="draw28@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    def _boom(_draw, _reading):
        raise RuntimeError("simulated post-draw failure")

    monkeypatch.setattr(reading_api_module, "_to_draw_summary", _boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/readings/{reading.id}/draws",
            json=_draw_payload(api_seeded_session),
            headers=_auth_header(owner),
        )

    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.DRAFTING


def test_unrelated_integrity_error_is_not_swallowed(seeded_session):
    """record_card_draw()'s IntegrityError backstop must only reinterpret
    the specific position-uniqueness violation as PositionAlreadyDrawnError
    -- a colliding draw_order (the sibling uq_card_draws_reading_id_draw_order
    constraint) must propagate unchanged, never be silently reinterpreted
    as a clean domain 409.

    Exercised as a direct service-function call (not through the HTTP API)
    because forcing this specific collision requires deterministically
    reproducing the same concurrent-race window
    Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md already
    accepts as out of scope for locking: every real HTTP request gets a
    freshly-queried Reading whose card_draws correctly reflects committed
    state, so a genuine collision cannot occur through the API in a
    single-threaded test. Here, `reading.card_draws` is deliberately
    accessed (and cached) *before* a second row is inserted directly at
    the table level (bypassing the ORM relationship, so the cached
    collection goes stale) -- exactly simulating what a second, truly
    concurrent writer would look like to record_card_draw()'s own
    max()+1 computation.
    """
    from sqlalchemy.exc import IntegrityError

    from app.services.reading_service import record_card_draw

    session = seeded_session
    spread = session.scalars(select(Spread).where(Spread.name == "Three Card")).one()
    deck = get_default_deck(session)
    pos_a = next(p for p in spread.positions if p.name == "Recent Past")
    pos_b = next(p for p in spread.positions if p.name == "Present Situation")
    card_a = get_card(session, deck, "The Fool")
    card_b = get_card(session, deck, "The Magician")

    reading = build_reading(session, spread_name="Three Card", draws=[])
    session.commit()

    _ = reading.card_draws  # cache an empty collection now, deliberately

    session.execute(
        CardDraw.__table__.insert().values(
            id=uuid.uuid4(),
            reading_id=reading.id,
            position_id=pos_a.id,
            card_id=card_a.id,
            orientation=Orientation.UPRIGHT.value,
            draw_order=1,
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
        record_card_draw(
            session, reading, position_id=pos_b.id, card_id=card_b.id, orientation=Orientation.UPRIGHT
        )


def test_response_contains_reading_status(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="draw30@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert "reading_status" in body
    assert body["reading_status"] == "drafting"
    assert set(body.keys()) == {
        "id",
        "position_id",
        "card_id",
        "orientation",
        "draw_order",
        "created_at",
        "reading_status",
    }


# =====================================================================================
# Reading retrieval -- GET /readings/{reading_id} (Step 43,
# Documentation/READING_DETAIL_API_DESIGN.md)
# =====================================================================================

_DETAIL_TOP_LEVEL_KEYS = {
    "id",
    "status",
    "question",
    "question_domain",
    "draw_method",
    "created_at",
    "updated_at",
    "spread_id",
    "spread",
    "deck_id",
    "card_draws",
}
_DETAIL_CARD_DRAW_KEYS = {"id", "position", "card", "orientation", "draw_order", "created_at"}


# --- Authorization ----------------------------------------------------------------


def test_owner_can_retrieve_their_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail1@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["id"] == str(reading.id)


def test_unauthenticated_retrieval_returns_401(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail2@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}")

    assert response.status_code == 401


def test_cross_user_retrieval_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail3@example.com")
    other = make_user(api_seeded_session, email="detail3other@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(other))

    assert response.status_code == 404


def test_unowned_reading_retrieval_fails_closed(api_seeded_session, client):
    user = make_user(api_seeded_session, email="detail4@example.com")
    api_seeded_session.commit()
    unowned = _empty_reading(api_seeded_session)
    assert unowned.reflection_session.owner_id is None

    response = client.get(f"/readings/{unowned.id}", headers=_auth_header(user))

    assert response.status_code == 404


def test_nonexistent_reading_retrieval_returns_404(api_seeded_session, client):
    user = make_user(api_seeded_session, email="detail5@example.com")
    api_seeded_session.commit()

    response = client.get(f"/readings/{uuid.uuid4()}", headers=_auth_header(user))

    assert response.status_code == 404


def test_cross_user_and_nonexistent_retrieval_return_identical_responses(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail6@example.com")
    other = make_user(api_seeded_session, email="detail6other@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    cross_user = client.get(f"/readings/{reading.id}", headers=_auth_header(other))
    nonexistent = client.get(f"/readings/{uuid.uuid4()}", headers=_auth_header(other))

    assert cross_user.status_code == nonexistent.status_code == 404
    assert cross_user.json() == nonexistent.json()


def test_malformed_reading_id_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail7@example.com")
    api_seeded_session.commit()

    response = client.get("/readings/not-a-uuid", headers=_auth_header(owner))

    assert response.status_code == 422


# --- Basic retrieval ----------------------------------------------------------------


def test_retrieval_of_a_reading_with_zero_draws(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail8@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["card_draws"] == []
    assert response.json()["status"] == "drafting"


def test_retrieval_of_a_reading_with_one_draw(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail9@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert len(response.json()["card_draws"]) == 1


def test_retrieval_of_a_reading_with_multiple_draws(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail10@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Present Situation", card_name="The Magician"),
        headers=_auth_header(owner),
    )

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert len(response.json()["card_draws"]) == 2


def test_retrieval_of_a_partially_completed_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail11@example.com")
    api_seeded_session.commit()
    reading = _drafting_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "drafting"
    assert len(response.json()["card_draws"]) == 1


def test_retrieval_of_a_completed_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail12@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "spread_complete"
    assert len(response.json()["card_draws"]) == 3


def test_retrieval_of_a_saved_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail13@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "saved"


# --- Embedded Spread ----------------------------------------------------------------


def test_embedded_spread_matches_the_readings_actual_spread(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail14@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    expected_spread = _seeded_spread(api_seeded_session)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    body = response.json()
    assert body["spread_id"] == str(expected_spread.id)
    assert body["spread"]["id"] == str(expected_spread.id)
    assert body["spread"]["name"] == "Three Card"


def test_embedded_spread_includes_all_positions(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail15@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    expected_spread = _seeded_spread(api_seeded_session)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    positions = response.json()["spread"]["positions"]
    assert len(positions) == len(expected_spread.positions) == 3
    assert {p["name"] for p in positions} == {p.name for p in expected_spread.positions}


def test_embedded_spread_positions_are_ordered_by_position_order(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail16@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    orders = [p["position_order"] for p in response.json()["spread"]["positions"]]
    assert orders == sorted(orders)


def test_embedded_spread_position_count_matches_the_actual_spread(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail17@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    body = response.json()
    assert body["spread"]["position_count"] == len(body["spread"]["positions"])


# --- Embedded CardDraws --------------------------------------------------------------


def test_embedded_card_draw_fields_match_the_persisted_row(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail18@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    position = _spread_position(api_seeded_session, "Recent Past")
    card = get_card(api_seeded_session, get_default_deck(api_seeded_session), "The Fool")

    client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(position.id), "card_id": str(card.id), "orientation": "reversed"},
        headers=_auth_header(owner),
    )

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    draw = response.json()["card_draws"][0]
    api_seeded_session.expire_all()
    persisted = api_seeded_session.execute(
        select(CardDraw).where(CardDraw.reading_id == reading.id)
    ).scalar_one()

    assert draw["id"] == str(persisted.id)
    assert draw["card"]["id"] == str(card.id)
    assert draw["card"]["name"] == "The Fool"
    assert draw["position"]["id"] == str(position.id)
    assert draw["position"]["name"] == "Recent Past"
    assert draw["orientation"] == "reversed"
    assert draw["draw_order"] == persisted.draw_order
    assert draw["created_at"] is not None
    assert set(draw.keys()) == _DETAIL_CARD_DRAW_KEYS


def test_embedded_card_draws_are_ordered_by_draw_order(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail19@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    # Recorded in a different sequence than position_order to prove the
    # response follows draw_order, not position_order or insertion order.
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Near Future", card_name="The Star"),
        headers=_auth_header(owner),
    )
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    draws = response.json()["card_draws"]
    assert [d["draw_order"] for d in draws] == [1, 2]
    assert draws[0]["position"]["name"] == "Near Future"
    assert draws[1]["position"]["name"] == "Recent Past"


# --- Lifecycle ------------------------------------------------------------------------


def test_status_accurately_reflects_the_database_across_the_lifecycle(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail20@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    assert client.get(f"/readings/{reading.id}", headers=_auth_header(owner)).json()["status"] == "drafting"

    deck = get_default_deck(api_seeded_session)
    for position_name, card_name in [
        ("Recent Past", "The Fool"),
        ("Present Situation", "The Magician"),
        ("Near Future", "The Star"),
    ]:
        client.post(
            f"/readings/{reading.id}/draws",
            json=_draw_payload(api_seeded_session, position_name=position_name, card_name=card_name),
            headers=_auth_header(owner),
        )
    assert (
        client.get(f"/readings/{reading.id}", headers=_auth_header(owner)).json()["status"]
        == "spread_complete"
    )

    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    assert (
        client.get(f"/readings/{reading.id}", headers=_auth_header(owner)).json()["status"] == "interpreted"
    )

    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))
    assert client.get(f"/readings/{reading.id}", headers=_auth_header(owner)).json()["status"] == "saved"


def test_optional_position_remains_visible_in_spread_when_undrawn(api_seeded_session, client):
    """No seeded spread has an optional position (Step 29/33's own
    finding, unchanged) -- constructed directly, mirroring the same
    technique those steps used.
    """
    owner = make_user(api_seeded_session, email="detail21@example.com")
    api_seeded_session.commit()
    deck = get_default_deck(api_seeded_session)

    spread = Spread(name="Optional Position Detail Test", allow_duplicate_cards=False)
    api_seeded_session.add(spread)
    api_seeded_session.flush()
    required_position = SpreadPosition(spread=spread, name="Required", position_order=1, required=True)
    optional_position = SpreadPosition(spread=spread, name="Optional", position_order=2, required=False)
    api_seeded_session.add_all([required_position, optional_position])
    api_seeded_session.flush()

    reflection_session = ReflectionSession(owner=owner)
    api_seeded_session.add(reflection_session)
    api_seeded_session.flush()
    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question="optional position detail probe",
    )
    api_seeded_session.add(reading)
    api_seeded_session.commit()

    fool = get_card(api_seeded_session, deck, "The Fool")
    client.post(
        f"/readings/{reading.id}/draws",
        json={"position_id": str(required_position.id), "card_id": str(fool.id), "orientation": "upright"},
        headers=_auth_header(owner),
    )

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    body = response.json()
    assert body["status"] == "spread_complete"
    position_names = {p["name"] for p in body["spread"]["positions"]}
    assert position_names == {"Required", "Optional"}
    drawn_position_names = {d["position"]["name"] for d in body["card_draws"]}
    assert drawn_position_names == {"Required"}
    optional = next(p for p in body["spread"]["positions"] if p["name"] == "Optional")
    assert optional["required"] is False


def test_completed_reading_remains_retrievable(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail22@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200


def test_saved_reading_remains_retrievable(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail23@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/save", headers=_auth_header(owner))

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "saved"


# --- Interpretation/narrative separation ----------------------------------------------


def test_retrieval_does_not_embed_interpretation_content(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail24@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    body = response.json()
    assert set(body.keys()) == _DETAIL_TOP_LEVEL_KEYS
    assert "interpretation" not in body
    assert "interpretations" not in body
    assert "interpretive_model" not in body
    assert "narrative" not in body


def test_retrieval_does_not_invoke_interpretation_orchestration(api_seeded_session, client, monkeypatch):
    owner = make_user(api_seeded_session, email="detail25@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    calls = []
    real = orchestration_module.interpret_reading

    def _spy(session, reading_arg):
        calls.append(reading_arg.id)
        return real(session, reading_arg)

    monkeypatch.setattr(orchestration_module, "interpret_reading", _spy)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert calls == []


def test_retrieval_does_not_invoke_narrative_generation(api_seeded_session, client, monkeypatch):
    owner = make_user(api_seeded_session, email="detail26@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    client.post(f"/readings/{reading.id}/interpret", headers=_auth_header(owner))

    calls = []
    real = orchestration_module.assemble_narrative

    def _spy(model):
        calls.append(model)
        return real(model)

    monkeypatch.setattr(orchestration_module, "assemble_narrative", _spy)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    assert response.status_code == 200
    assert calls == []


# --- Security / data exposure ---------------------------------------------------------


def test_retrieval_response_exposes_no_sensitive_or_internal_fields(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="detail27@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)

    response = client.get(f"/readings/{reading.id}", headers=_auth_header(owner))

    raw = response.text
    assert "hashed_password" not in raw
    assert "owner_id" not in raw
    assert "reflection_session_id" not in raw
    assert "access_token" not in raw

    body = response.json()
    assert set(body.keys()) == _DETAIL_TOP_LEVEL_KEYS
    assert set(body["spread"].keys()) == {
        "id",
        "name",
        "description",
        "position_count",
        "allow_duplicate_cards",
        "positions",
    }
    for position in body["spread"]["positions"]:
        assert "spread_id" not in position
    for draw in body["card_draws"]:
        assert set(draw.keys()) == _DETAIL_CARD_DRAW_KEYS
        assert "deck_id" not in draw["card"]
        assert "base_meaning_upright" not in draw["card"]
        assert "base_meaning_reversed" not in draw["card"]


# --- Query behavior ---------------------------------------------------------------------


def test_retrieval_of_a_fully_drawn_celtic_cross_does_not_exhibit_n_plus_1(api_seeded_session, client):
    """Proves the selectinload strategy avoids N+1 behavior for the
    worst-case seeded spread (10 positions): naive lazy loading would
    issue roughly 1 (Spread) + 1 (positions) + 1 (card_draws) + 10
    (each draw's position) + 10 (each draw's card) = ~23 queries for
    the detail fetch alone, scaling linearly with position count. A
    single request's query count staying well under that -- a generous,
    stable ceiling rather than one magic number -- is sufficient to
    catch a regression back to per-row lazy loading without depending
    on a fragile exact count or a delicate multi-request comparison
    (a two-request relative comparison was tried and found to be
    susceptible to an unrelated duplicate-query artifact on the first
    request of a fresh TestClient sequence, unrelated to this route's
    own query behavior -- confirmed by an isolated, non-pytest
    reproduction showing a stable, identical query count for both a
    1-draw and a 10-draw Reading).
    """
    owner = make_user(api_seeded_session, email="detail28@example.com")
    api_seeded_session.commit()

    celtic_cross = api_seeded_session.scalars(
        select(Spread).where(Spread.name == "Celtic Cross")
    ).one()
    deck = get_default_deck(api_seeded_session)
    positions = list(celtic_cross.positions)
    all_cards = list(
        api_seeded_session.scalars(select(Card).where(Card.deck_id == deck.id)).all()
    )

    created = client.post(
        "/readings",
        json={"spread_id": str(celtic_cross.id), "question": "query-count probe"},
        headers=_auth_header(owner),
    ).json()
    reading_id = created["id"]
    for position, card in zip(positions, all_cards):
        response = client.post(
            f"/readings/{reading_id}/draws",
            json={"position_id": str(position.id), "card_id": str(card.id), "orientation": "upright"},
            headers=_auth_header(owner),
        )
        assert response.status_code == 201

    query_log: list[str] = []
    engine = api_seeded_session.get_bind()

    def _log(conn, cursor, statement, parameters, context, executemany):
        query_log.append(statement)

    event.listen(engine, "before_cursor_execute", _log)
    try:
        response = client.get(f"/readings/{reading_id}", headers=_auth_header(owner))
    finally:
        event.remove(engine, "before_cursor_execute", _log)

    assert response.status_code == 200
    assert len(response.json()["card_draws"]) == 10
    # A naive per-row lazy-loading implementation would issue at least
    # ~20 queries for 10 draws (Section 8,
    # Documentation/READING_DETAIL_API_DESIGN.md); the selectinload
    # strategy keeps this small and constant regardless of draw count.
    assert len(query_log) < 15


# --- Integration ------------------------------------------------------------------------


def test_full_lifecycle_retrieval_reflects_accumulated_state(api_seeded_session, client):
    """register -> create -> retrieve -> draw -> retrieve -> complete ->
    interpret -> save -> retrieve, verifying the response accurately
    reflects state accumulated across the *entire* prior lifecycle, not
    merely its own isolated write. Also proves another user cannot
    retrieve it.
    """
    register = client.post(
        "/auth/register", json={"email": "lifecycle@example.com", "password": "correct horse battery staple"}
    )
    assert register.status_code == 201
    login = client.post(
        "/auth/login", json={"email": "lifecycle@example.com", "password": "correct horse battery staple"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    spread = _seeded_spread(api_seeded_session)
    created = client.post(
        "/readings", json={"spread_id": str(spread.id), "question": "Full lifecycle probe"}, headers=headers
    ).json()
    reading_id = created["id"]

    detail_empty = client.get(f"/readings/{reading_id}", headers=headers)
    assert detail_empty.status_code == 200
    assert detail_empty.json()["card_draws"] == []
    assert detail_empty.json()["status"] == "drafting"

    deck = get_default_deck(api_seeded_session)
    draws_plan = [
        ("Recent Past", "The Fool", "upright"),
        ("Present Situation", "The Magician", "reversed"),
        ("Near Future", "The Star", "upright"),
    ]
    for position_name, card_name, orientation in draws_plan:
        position = _spread_position(api_seeded_session, position_name)
        card = get_card(api_seeded_session, deck, card_name)
        resp = client.post(
            f"/readings/{reading_id}/draws",
            json={"position_id": str(position.id), "card_id": str(card.id), "orientation": orientation},
            headers=headers,
        )
        assert resp.status_code == 201

    detail_drawn = client.get(f"/readings/{reading_id}", headers=headers)
    assert detail_drawn.status_code == 200
    body_drawn = detail_drawn.json()
    assert body_drawn["status"] == "spread_complete"
    assert len(body_drawn["card_draws"]) == 3
    drawn_cards = {d["card"]["name"] for d in body_drawn["card_draws"]}
    assert drawn_cards == {"The Fool", "The Magician", "The Star"}
    reversed_draws = [d for d in body_drawn["card_draws"] if d["orientation"] == "reversed"]
    assert len(reversed_draws) == 1
    assert reversed_draws[0]["card"]["name"] == "The Magician"

    interpret_resp = client.post(f"/readings/{reading_id}/interpret", headers=headers)
    assert interpret_resp.status_code == 201

    save_resp = client.post(f"/readings/{reading_id}/save", headers=headers)
    assert save_resp.status_code == 200

    detail_saved = client.get(f"/readings/{reading_id}", headers=headers)
    assert detail_saved.status_code == 200
    assert detail_saved.json()["status"] == "saved"
    assert len(detail_saved.json()["card_draws"]) == 3

    other_register = client.post(
        "/auth/register", json={"email": "lifecycle_other@example.com", "password": "correct horse battery staple"}
    )
    assert other_register.status_code == 201
    other_login = client.post(
        "/auth/login", json={"email": "lifecycle_other@example.com", "password": "correct horse battery staple"}
    )
    other_token = other_login.json()["access_token"]

    other_detail = client.get(
        f"/readings/{reading_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert other_detail.status_code == 404


# =====================================================================================
# Digital Draw -- POST /readings/{reading_id}/draws/digital
# (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 8.2)
# =====================================================================================


def _build_digital_reading(
    session: Session, spread: Spread, deck: Deck, owner: User | None = None
) -> Reading:
    """A DRAFTING, draw_method=DIGITAL Reading against the given Spread/
    Deck, with zero CardDraw rows -- built directly (mirrors
    tests/interpretation_helpers.py::build_reading(), which has no
    draw_method parameter) rather than extending that shared helper for
    a single call site.
    """
    reflection_session = ReflectionSession(owner=owner)
    session.add(reflection_session)
    session.flush()
    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question="What should I focus on right now?",
        draw_method=DrawMethod.DIGITAL,
    )
    session.add(reading)
    session.commit()
    return reading


def _empty_digital_reading(session: Session, owner: User | None = None, spread_name: str = "Three Card") -> Reading:
    """A DRAFTING, draw_method=DIGITAL "Three Card" Reading against the
    real seeded Spread/Deck -- the starting point for every positive-path
    digital-draw test, mirroring _empty_reading above.
    """
    return _build_digital_reading(session, _seeded_spread(session, spread_name), get_default_deck(session), owner)


def test_digital_draw_returns_201(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital1@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 201


def test_digital_draw_returns_the_correct_number_of_card_draws(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital2@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert len(response.json()) == 3


def test_digital_draw_fills_every_spread_position_exactly_once(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital3@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)
    expected_position_ids = {str(p.id) for p in _seeded_spread(api_seeded_session).positions}

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    drawn_position_ids = [draw["position_id"] for draw in response.json()]
    assert set(drawn_position_ids) == expected_position_ids
    assert len(drawn_position_ids) == len(set(drawn_position_ids))


def test_digital_draw_cards_belong_to_the_readings_deck(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital4@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)
    deck_card_ids = {str(c.id) for c in get_default_deck(api_seeded_session).cards}

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    drawn_card_ids = {draw["card_id"] for draw in response.json()}
    assert drawn_card_ids.issubset(deck_card_ids)


def test_digital_draw_order_is_sequential_from_one(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital5@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert sorted(draw["draw_order"] for draw in response.json()) == [1, 2, 3]


def test_digital_draw_transitions_reading_to_spread_complete(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital6@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert all(draw["reading_status"] == "spread_complete" for draw in response.json())
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.SPREAD_COMPLETE


def test_digital_draw_persists_through_the_same_card_draw_table(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital7@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    api_seeded_session.expire_all()
    persisted = api_seeded_session.execute(
        select(CardDraw).where(CardDraw.reading_id == reading.id)
    ).scalars().all()
    assert len(persisted) == 3


def test_digital_draw_orientation_values_are_valid(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital8@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert all(draw["orientation"] in ("upright", "reversed") for draw in response.json())


def test_digital_draw_no_duplicate_cards_when_spread_disallows_them(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital9@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)
    assert _seeded_spread(api_seeded_session).allow_duplicate_cards is False

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    card_ids = [draw["card_id"] for draw in response.json()]
    assert len(card_ids) == len(set(card_ids))


def test_digital_draw_allows_duplicate_cards_when_spread_permits_it(api_seeded_session, client):
    """No seeded Spread allows duplicates (test_optional_position_remains_
    visible_in_spread_when_undrawn above notes the same gap for optional
    positions) -- a custom single-card Deck + a duplicate-permitting
    Spread makes a duplicate the only possible outcome, deterministically.
    """
    owner = make_user(api_seeded_session, email="digital10@example.com")
    deck = make_deck(api_seeded_session, name="Single Card Deck", is_default=False)
    card = make_major_card(api_seeded_session, deck, name="The Fool")
    spread = make_spread(
        api_seeded_session,
        name="Duplicate-Friendly Spread",
        allow_duplicate_cards=True,
        position_names=("First", "Second", "Third"),
    )
    api_seeded_session.commit()
    reading = _build_digital_reading(api_seeded_session, spread, deck, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 201
    card_ids = {draw["card_id"] for draw in response.json()}
    assert card_ids == {str(card.id)}


def test_digital_draw_with_insufficient_cards_returns_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital11@example.com")
    deck = make_deck(api_seeded_session, name="Too Small Deck", is_default=False)
    make_major_card(api_seeded_session, deck, name="The Fool")
    make_major_card(api_seeded_session, deck, name="The Magician")
    spread = make_spread(
        api_seeded_session, name="Three Slot Spread", allow_duplicate_cards=False, position_names=("A", "B", "C")
    )
    api_seeded_session.commit()
    reading = _build_digital_reading(api_seeded_session, spread, deck, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []


def test_digital_draw_against_a_physical_reading_returns_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital12@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)
    assert reading.draw_method == DrawMethod.PHYSICAL

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 409
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []


def test_digital_draw_against_an_already_spread_complete_reading_returns_409(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital13@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)
    first = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))
    assert first.status_code == 201

    second = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert second.status_code == 409
    api_seeded_session.expire_all()
    assert len(api_seeded_session.get(Reading, reading.id).card_draws) == 3  # unchanged, not doubled


def test_digital_draw_against_a_reading_with_an_existing_manual_draw_returns_409(api_seeded_session, client):
    """A DIGITAL, still-DRAFTING reading that already has one manually-
    recorded CardDraw -- reachable only because the manual /draws endpoint
    does not itself check draw_method -- is rejected: Digital Draw is
    whole-spread and atomic, never a top-up.
    """
    owner = make_user(api_seeded_session, email="digital14@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)
    client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session, position_name="Recent Past", card_name="The Fool"),
        headers=_auth_header(owner),
    )
    api_seeded_session.expire_all()
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.DRAFTING

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 409


def test_digital_draw_unauthenticated_returns_401(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital15@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital")

    assert response.status_code == 401


def test_digital_draw_against_nonexistent_reading_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital16@example.com")
    api_seeded_session.commit()

    response = client.post(f"/readings/{uuid.uuid4()}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 404


def test_digital_draw_cross_user_returns_404(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital17@example.com")
    other = make_user(api_seeded_session, email="digital17other@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(other))

    assert response.status_code == 404
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []


def test_digital_draw_against_unowned_reading_fails_closed(api_seeded_session, client):
    user = make_user(api_seeded_session, email="digital18@example.com")
    api_seeded_session.commit()
    unowned = _empty_digital_reading(api_seeded_session)
    assert unowned.reflection_session.owner_id is None

    response = client.post(f"/readings/{unowned.id}/draws/digital", headers=_auth_header(user))

    assert response.status_code == 404


def test_digital_draw_malformed_reading_id_returns_422(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital19@example.com")
    api_seeded_session.commit()

    response = client.post("/readings/not-a-uuid/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 422


def test_digital_draw_response_item_shape(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="digital20@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    response = client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    assert response.status_code == 201
    for draw in response.json():
        assert set(draw.keys()) == {
            "id", "position_id", "card_id", "orientation", "draw_order", "created_at", "reading_status",
        }


def test_digital_draw_transaction_rollback_on_forced_post_flush_failure(api_seeded_session, client, monkeypatch):
    """Mirrors test_transaction_rollback_on_forced_post_flush_failure for
    manual draws: forces a failure after record_digital_draw() has
    already flushed all three CardDraw rows, proving get_db()'s single
    commit point discards them together -- atomicity of the request as a
    whole, not merely within record_digital_draw() itself.
    """
    owner = make_user(api_seeded_session, email="digital21@example.com")
    api_seeded_session.commit()
    reading = _empty_digital_reading(api_seeded_session, owner)

    def _boom(_draw, _reading):
        raise RuntimeError("simulated post-draw failure")

    monkeypatch.setattr(reading_api_module, "_to_draw_summary", _boom)

    with pytest.raises(RuntimeError):
        client.post(f"/readings/{reading.id}/draws/digital", headers=_auth_header(owner))

    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).all() == []
    assert api_seeded_session.get(Reading, reading.id).status == ReadingStatus.DRAFTING


def test_manual_draw_endpoint_is_unaffected_by_digital_draw(api_seeded_session, client):
    """Sanity check that adding the digital-draw route/service did not
    alter manual entry's own behavior -- the full pre-existing suite
    above already re-verifies this in depth; this is a single, direct
    regression probe alongside the new tests.
    """
    owner = make_user(api_seeded_session, email="digital22@example.com")
    api_seeded_session.commit()
    reading = _empty_reading(api_seeded_session, owner)

    response = client.post(
        f"/readings/{reading.id}/draws",
        json=_draw_payload(api_seeded_session),
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["reading_status"] == "drafting"
