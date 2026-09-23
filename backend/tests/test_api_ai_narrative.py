"""API tests for the AI Narrative Layer
(POST /readings/{reading_id}/ai-narrative,
GET /readings/{reading_id}/ai-narrative/current).

Self-contained fixtures, mirroring tests/test_api_scripture.py's own
established pattern exactly -- this file additionally overrides
get_reflection_engine_client with a FakeReflectionEngineClient (see
tests/reflection_engine_fakes.py) so no test here makes a real AI provider
call.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_reflection_engine_client
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import Base, Orientation, ScriptureReference, User
from app.models.reading import Reading
from app.seed.seed import seed_reference_data
from tests.factories import make_user
from tests.interpretation_helpers import build_reading
from tests.reflection_engine_fakes import FakeReflectionEngineClient, valid_content_with

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


def _matched_reading(session: Session, owner: User) -> Reading:
    """A Single Card reading of The Star -- its own first authored theme
    is "hope", which has a real approved Scripture mapping (Romans
    15:13) in the seeded dataset. See tests/test_api_scripture.py's own
    _matched_reading() docstring for why _complete_reading()'s Celtic
    Cross fixture no longer produces a match (its central_issue,
    "inner_guidance", has no approved mapping under the single-theme,
    no-cross-theme-fallback selection rule).
    """
    return build_reading(
        session, spread_name="Single Card", draws=[("The Card", "The Star", Orientation.UPRIGHT)], owner=owner
    )


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
def fake_ai_client() -> FakeReflectionEngineClient:
    return FakeReflectionEngineClient()


@pytest.fixture()
def client(api_session_factory, auth_headers, fake_ai_client):
    from app.main import app

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
    app.dependency_overrides[get_reflection_engine_client] = lambda: fake_ai_client
    with TestClient(app) as test_client:
        test_client.headers.update(auth_headers)
        yield test_client
    app.dependency_overrides.clear()


# --- Successful generation ---------------------------------------------------------


def test_generate_route_returns_201_and_the_structured_response(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 201
    body = response.json()
    assert body["ai_narrative"]["provider"] == "anthropic"
    assert len(body["ai_narrative"]["key_themes"]) >= 1
    assert len(body["ai_narrative"]["reflection_questions"]) >= 1
    assert body["ai_narrative"]["scriptural_reflection"] is None


def test_generate_route_supplies_the_real_deterministic_data_to_the_ai_layer(
    api_seeded_session, client, owner, fake_ai_client
):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    client.post(f"/readings/{reading.id}/ai-narrative")

    assert len(fake_ai_client.calls) == 1
    user_prompt = fake_ai_client.calls[0]["user_prompt"]
    assert "Scripture smoke test question" not in user_prompt  # sanity: not the smoke-test fixture
    payload = json.loads(user_prompt.split("READING DATA (JSON):\n\n")[1])
    assert payload["interpretation"]["spread_name"] == "Celtic Cross"
    assert payload["scripture"] is None


# --- Scripture: opt-in only ---------------------------------------------------------


def test_generate_route_defaults_to_no_scripture(api_seeded_session, client, owner, fake_ai_client):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 201
    assert '"scripture": null' in fake_ai_client.calls[0]["user_prompt"]


def test_generate_route_include_scripture_true_supplies_scripture_and_allows_it_in_the_response(
    api_seeded_session, client, owner, fake_ai_client
):
    """The Star's own first authored theme, "hope", has a real approved
    mapping in the seed data -- proving the full pipeline (engine ->
    single-theme selection -> Scripture selection -> AI Narrative input)
    connects end to end.
    """
    reading = _matched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    fake_ai_client.response_text = json.dumps(
        valid_content_with(scriptural_reflection="Romans speaks to hope in this reading.")
    )

    response = client.post(f"/readings/{reading.id}/ai-narrative", params={"include_scripture": "true"})

    assert response.status_code == 201
    assert response.json()["ai_narrative"]["scriptural_reflection"] == "Romans speaks to hope in this reading."
    payload = json.loads(fake_ai_client.calls[0]["user_prompt"].split("READING DATA (JSON):\n\n")[1])
    assert payload["scripture"] is not None
    assert payload["scripture"]["reflections"]


def _unmatched_reading(session: Session, owner: User) -> Reading:
    """A Single Card reading of The Chariot, with its own three Scripture
    candidate themes (determination, focus, momentum -- major_arcana.yaml's
    own authored primary/secondary themes) verified to have *no* approved
    mapping through this specific request -- proving the "opted in but
    nothing found" path stays graceful: no error, and no snapshot
    persisted.

    The Chariot alone no longer guarantees this: since the second
    Scripture coverage expansion batch, two of its three candidates
    (determination, focus) are themselves approved themes -- at 89 of
    107 controlled themes now mapped, no real Single Card or Three Card
    combination of drawn cards produces a naturally empty result any
    more (every card carries at least one now-covered theme; see
    tests/test_api_scripture.py's own identically-named fixture for the
    full explanation). This fixture deliberately removes just the two
    ScriptureReference rows that would otherwise match this one
    reading's own candidates -- "momentum" is untouched and remains a
    genuine, Tier-3, deliberately unmapped theme.
    """
    reading = build_reading(
        session, spread_name="Single Card", draws=[("The Card", "The Chariot", Orientation.UPRIGHT)], owner=owner
    )
    session.execute(
        ScriptureReference.__table__.delete().where(ScriptureReference.theme.in_(("determination", "focus")))
    )
    session.commit()
    return reading


# --- AI Narrative + Scriptural Reflection integration (Raidian Reading Lifecycle
# improvements): checking "include Scripture" must itself surface the Scriptural
# Perspective, not merely weave it into the AI text ----------------------------------


def test_include_scripture_true_persists_a_scripture_snapshot_as_a_side_effect(
    api_seeded_session, client, owner, fake_ai_client
):
    """The reported UX gap: checking "include Scripture" when generating
    an AI Narrative must not require a separate, subsequent GET
    /scripture call to make the Scriptural Perspective available to the
    rest of the page -- generating with include_scripture=true must
    itself leave a ScripturalReflection snapshot persisted, exactly as
    GET /scripture would.
    """
    reading = _matched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(f"/readings/{reading.id}/ai-narrative", params={"include_scripture": "true"})
    assert response.status_code == 201

    current = client.get(f"/readings/{reading.id}/scripture/current")
    assert current.status_code == 200
    assert current.json()["reflections"]


def test_include_scripture_false_does_not_persist_a_scripture_snapshot(
    api_seeded_session, client, owner, fake_ai_client
):
    """Preserves the existing AI-Narrative-only behavior when the
    checkbox is unchecked (the default): no Scripture snapshot appears
    as a side effect of a plain AI Narrative generation.
    """
    reading = _matched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(f"/readings/{reading.id}/ai-narrative")
    assert response.status_code == 201

    current = client.get(f"/readings/{reading.id}/scripture/current")
    assert current.status_code == 404


def test_include_scripture_true_does_not_duplicate_an_already_persisted_snapshot(
    api_seeded_session, client, owner, fake_ai_client
):
    """A Scripture snapshot already persisted (via an earlier GET
    /scripture call) is reused as-is by a later include_scripture=true
    generation -- never recomputed into a second, possibly-different
    snapshot.
    """
    reading = _matched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    first = client.get(f"/readings/{reading.id}/scripture")
    assert first.status_code == 200
    assert first.json()["reflections"]

    response = client.post(f"/readings/{reading.id}/ai-narrative", params={"include_scripture": "true"})
    assert response.status_code == 201

    second = client.get(f"/readings/{reading.id}/scripture/current")
    assert second.status_code == 200
    assert {k: v for k, v in second.json().items() if k != "generated_at"} == {
        k: v for k, v in first.json().items() if k != "generated_at"
    }


def test_include_scripture_true_with_no_approved_match_succeeds_without_error(
    api_seeded_session, client, owner, fake_ai_client
):
    """Opting in to Scripture for a reading whose themes have no approved
    reference must not surface as an error -- AI Narrative generation
    still succeeds, with scripture omitted from its own response, and no
    ScripturalReflection snapshot is persisted (an empty selection is
    never persisted -- see get_scripture_for_reading's own docstring).
    """
    reading = _unmatched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(f"/readings/{reading.id}/ai-narrative", params={"include_scripture": "true"})

    assert response.status_code == 201
    assert response.json()["ai_narrative"]["scriptural_reflection"] is None
    payload = json.loads(fake_ai_client.calls[0]["user_prompt"].split("READING DATA (JSON):\n\n")[1])
    assert payload["scripture"] is not None
    assert payload["scripture"]["reflections"] == []
    current = client.get(f"/readings/{reading.id}/scripture/current")
    assert current.status_code == 404


def test_generate_route_rejects_a_response_that_invents_scripture_when_not_requested(
    api_seeded_session, client, owner, fake_ai_client
):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    fake_ai_client.response_text = json.dumps(valid_content_with(scriptural_reflection="A fabricated verse."))

    response = client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 502


# --- Malformed / failed generation never corrupts the deterministic reading --------


def test_generate_route_502_on_malformed_ai_response(api_seeded_session, client, owner, fake_ai_client):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    fake_ai_client.response_text = "not valid json"

    response = client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 502


def test_failed_generation_leaves_the_deterministic_interpretation_untouched_and_creates_no_ai_narrative_row(
    api_seeded_session, client, owner, fake_ai_client
):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    before = client.get(f"/readings/{reading.id}/interpretations/current").json()
    fake_ai_client.response_text = "not valid json"

    generate_response = client.post(f"/readings/{reading.id}/ai-narrative")
    after = client.get(f"/readings/{reading.id}/interpretations/current").json()
    current_ai_narrative = client.get(f"/readings/{reading.id}/ai-narrative/current")

    assert generate_response.status_code == 502
    assert before == after
    assert current_ai_narrative.status_code == 404


def test_generate_route_returns_503_when_the_reflection_engine_is_not_configured(
    api_seeded_session, auth_headers, api_session_factory, owner
):
    """No dependency override here -- the real AnthropicReflectionEngineClient
    is constructed with the default, blank RAIDIAN_AI_API_KEY (see
    app/core/config.py), which fails closed before any network call is
    attempted (AnthropicReflectionEngineClient.complete()'s own first
    check) -- so this exercises the true "not configured" path safely.
    """
    from app.main import app

    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    def _override_get_db():
        db = api_session_factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as unconfigured_client:
            unconfigured_client.headers.update(auth_headers)
            unconfigured_client.post(f"/readings/{reading.id}/interpret")
            response = unconfigured_client.post(f"/readings/{reading.id}/ai-narrative")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


# --- Never interpreted --------------------------------------------------------------


def test_generate_route_404_when_never_interpreted(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 404


def test_get_current_route_404_before_any_generation(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.get(f"/readings/{reading.id}/ai-narrative/current")

    assert response.status_code == 404


# --- History / idempotency ----------------------------------------------------------


def test_repeated_generation_creates_new_rows_and_get_current_returns_the_latest(
    api_seeded_session, client, owner, fake_ai_client
):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    fake_ai_client.response_text = json.dumps(valid_content_with(opening_summary="First attempt."))
    first = client.post(f"/readings/{reading.id}/ai-narrative")
    fake_ai_client.response_text = json.dumps(valid_content_with(opening_summary="Second attempt."))
    second = client.post(f"/readings/{reading.id}/ai-narrative")

    current = client.get(f"/readings/{reading.id}/ai-narrative/current")

    assert first.json()["id"] != second.json()["id"]
    assert current.json()["ai_narrative"]["opening_summary"] == "Second attempt."


# --- Independence from the other layers ---------------------------------------------


def test_ai_narrative_calls_never_alter_interpretation_narrative_or_scripture(
    api_seeded_session, client, owner
):
    """Narrative and Scripture are recomputed fresh on every call (their
    own established, never-cached design -- see
    SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md), so `generated_at` alone
    is expected to differ between calls even with nothing else changed;
    every other field must be identical.
    """
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    before_interpretation = client.get(f"/readings/{reading.id}/interpretations/current").json()
    before_narrative = client.get(f"/readings/{reading.id}/narrative").json()
    before_scripture = client.get(f"/readings/{reading.id}/scripture").json()

    client.post(f"/readings/{reading.id}/ai-narrative")

    after_narrative = client.get(f"/readings/{reading.id}/narrative").json()
    after_scripture = client.get(f"/readings/{reading.id}/scripture").json()
    assert client.get(f"/readings/{reading.id}/interpretations/current").json() == before_interpretation
    assert {k: v for k, v in after_narrative.items() if k != "generated_at"} == {
        k: v for k, v in before_narrative.items() if k != "generated_at"
    }
    assert {k: v for k, v in after_scripture.items() if k != "generated_at"} == {
        k: v for k, v in before_scripture.items() if k != "generated_at"
    }


def test_interpret_route_response_never_contains_ai_narrative_fields(api_seeded_session, client, owner):
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")

    assert "opening_summary" not in response.json()
    assert "reflection_questions" not in response.json()


# --- Ownership / authentication ------------------------------------------------------


def test_generate_route_requires_authentication(api_seeded_session, client, owner, auth_headers):
    from app.main import app

    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post(f"/readings/{reading.id}/ai-narrative")

    assert response.status_code == 401


def test_generate_route_cross_user_returns_404(api_seeded_session, client, owner):
    other = make_user(api_seeded_session, email="other@example.com")
    api_seeded_session.commit()
    reading = _complete_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    response = client.post(
        f"/readings/{reading.id}/ai-narrative",
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )

    assert response.status_code == 404


def test_generate_route_nonexistent_reading_returns_404(client):
    response = client.post(f"/readings/{uuid.uuid4()}/ai-narrative")

    assert response.status_code == 404


# --- Delete Saved Reading cascades through AINarrative/ScripturalReflection ---------


def test_deleting_a_reading_cascades_to_ai_narrative_and_scriptural_reflection(
    api_seeded_session, client, owner, fake_ai_client
):
    """Delete Saved Reading (Raidian Reading Lifecycle improvements): the
    cascade must reach every row an AI Narrative generation with Scripture
    included leaves behind, not just CardDraw/Interpretation -- verified
    directly against real AINarrative/ScripturalReflection rows, not just
    inferred from the FK configuration.
    """
    from app.models.ai_narrative import AINarrative
    from app.models.scriptural_reflection import ScripturalReflection

    reading = _matched_reading(api_seeded_session, owner)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")
    client.post(f"/readings/{reading.id}/ai-narrative", params={"include_scripture": "true"})
    client.post(f"/readings/{reading.id}/save")
    reading_id = reading.id

    api_seeded_session.expire_all()
    assert len(api_seeded_session.execute(select(AINarrative)).all()) == 1
    assert len(api_seeded_session.execute(select(ScripturalReflection)).all()) == 1

    response = client.delete(f"/readings/{reading_id}")

    assert response.status_code == 204
    api_seeded_session.expire_all()
    assert api_seeded_session.execute(select(AINarrative)).all() == []
    assert api_seeded_session.execute(select(ScripturalReflection)).all() == []
