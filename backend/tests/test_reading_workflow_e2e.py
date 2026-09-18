"""End-to-end workflow validation (Step 12,
Documentation/READING_WORKFLOW_VALIDATION.md).

Traces the complete implemented path:

    Reading -> POST .../interpret -> interpret_reading() -> engine.interpret()
    -> save_interpretation() -> DB -> GET .../interpretations/current
    -> get_current_interpretation() -> InterpretiveModel
    -> GET .../narrative -> assemble_narrative() -> NarrativeModel

This is a validation suite, not a new feature's own unit tests -- it
deliberately cross-checks independently-taken paths (e.g. a directly
computed engine result vs. the same content retrieved back through the
full API) rather than re-testing what test_reading_orchestration.py and
test_api_interpretation.py (Steps 9/11) already cover in isolation.

Fixtures are self-contained, mirroring test_api_interpretation.py's own
rationale: a `client` fixture needs a `get_db` override bound to a
StaticPool in-memory SQLite engine shared across every request a test
makes.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.interpretation.engine as engine_module
from app.db.session import get_db
from app.main import app
from app.models import Base, Interpretation, Orientation, Reading, ReadingStatus
from app.models.enums import Suit
from app.seed.seed import seed_reference_data
from app.services import reading_orchestration
from app.services.interpretation.engine import interpret as engine_interpret
from app.services.interpretation.relationships import CardRelationships, SuitCluster
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


def _complete_reading(session: Session) -> Reading:
    return build_reading(session, spread_name="Celtic Cross", draws=_FULL_CELTIC_CROSS_DRAWS)


def _incomplete_reading(session: Session) -> Reading:
    return build_reading(
        session,
        spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Challenge", "The Tower", Orientation.UPRIGHT),
        ],
    )


def _minimal_model_dict(central_issue_value: str = "new_beginnings") -> dict:
    return {
        "schema_version": "1.0",
        "engine_version": "0.1.0-foundation",
        "reference_data_version": "deadbeef",
        "generated_at": "2026-09-18T00:00:00Z",
        "central_question": "What should I focus on?",
        "central_issue": {
            "value": central_issue_value,
            "citations": [{"source_type": "card_draw"}],
        },
        "primary_tension": None,
        "supporting_themes": [],
        "trajectory": None,
        "blocker": None,
        "uncertainty": [],
        "advice": None,
        "clarification": None,
        "contradictions": [],
        "evidence_strength": "unresolved",
    }


# --- Fixtures --------------------------------------------------------------------


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


# --- 1/2/3/4/6: the full chain, traced hop by hop --------------------------------


def test_full_workflow_trace_interpret_persist_retrieve_narrative(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()
    assert reading.status == ReadingStatus.DRAFTING

    # Hop 1: POST .../interpret
    post_response = client.post(f"/readings/{reading.id}/interpret")
    assert post_response.status_code == 201
    posted = post_response.json()

    # Hop 2: the Interpretation was actually persisted (raw DB check,
    # bypassing every service/API layer).
    api_seeded_session.expire_all()
    persisted = api_seeded_session.execute(
        select(Interpretation).where(Interpretation.reading_id == reading.id)
    ).scalar_one()
    assert str(persisted.id) == posted["id"]
    assert persisted.interpretive_model["central_issue"]["value"] == posted["interpretive_model"]["central_issue"]["value"]

    # Hop 3: Reading.status transitioned.
    reloaded_reading = api_seeded_session.get(Reading, reading.id)
    assert reloaded_reading.status == ReadingStatus.INTERPRETED

    # Hop 4: GET .../interpretations/current returns exactly that row.
    current_response = client.get(f"/readings/{reading.id}/interpretations/current")
    assert current_response.status_code == 200
    assert current_response.json()["id"] == posted["id"]
    assert current_response.json()["interpretive_model"] == posted["interpretive_model"]

    # Hop 5: GET .../narrative derives from that same Interpretation.
    narrative_response = client.get(f"/readings/{reading.id}/narrative")
    assert narrative_response.status_code == 200
    narrative = narrative_response.json()
    assert narrative["source_engine_version"] == posted["engine_version"]
    assert narrative["source_reference_data_version"] == posted["reference_data_version"]
    central_theme_section = next(s for s in narrative["sections"] if s["id"] == "central_theme")
    assert central_theme_section["present"] is True
    assert central_theme_section["statements"]


# --- 5: retrieved model matches what the engine actually produced ---------------


def test_retrieved_interpretive_model_matches_the_engine_output(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    directly_computed = engine_interpret(reading, api_seeded_session)

    response = client.post(f"/readings/{reading.id}/interpret")
    assert response.status_code == 201
    retrieved = response.json()["interpretive_model"]

    expected = directly_computed.model_dump(mode="json", exclude={"generated_at"})
    actual = {key: value for key, value in retrieved.items() if key != "generated_at"}
    assert actual == expected


# --- 6/9: narrative derives from the current (highest-sequence) Interpretation ---


def test_narrative_reflects_the_current_highest_sequence_interpretation(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    stale = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict("stale_theme"), sequence=1,
    )
    api_seeded_session.add(stale)
    current = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict("current_theme"), sequence=2,
    )
    api_seeded_session.add(current)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/narrative")
    assert response.status_code == 200
    sections = response.json()["sections"]
    central_theme_section = next(s for s in sections if s["id"] == "central_theme")
    assert central_theme_section["statements"][0]["text"] == "Current Theme"


def test_current_endpoint_uses_sequence_not_insertion_order(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    row_a = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict("theme_a"), sequence=100,
    )
    api_seeded_session.add(row_a)
    api_seeded_session.flush()
    row_b = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict("theme_b"), sequence=1,
    )
    api_seeded_session.add(row_b)
    api_seeded_session.commit()

    response = client.get(f"/readings/{reading.id}/interpretations/current")
    assert response.status_code == 200
    assert response.json()["id"] == str(row_a.id)  # inserted first, but higher sequence


# --- 7: narrative generation writes nothing --------------------------------------


def test_narrative_generation_creates_no_rows_and_does_not_mutate_the_reading(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    api_seeded_session.expire_all()
    interpretation_count_before = len(
        api_seeded_session.execute(
            select(Interpretation).where(Interpretation.reading_id == reading.id)
        ).all()
    )
    reading_updated_at_before = api_seeded_session.get(Reading, reading.id).updated_at

    first = client.get(f"/readings/{reading.id}/narrative")
    second = client.get(f"/readings/{reading.id}/narrative")
    assert first.status_code == 200
    assert second.status_code == 200

    api_seeded_session.expire_all()
    interpretation_count_after = len(
        api_seeded_session.execute(
            select(Interpretation).where(Interpretation.reading_id == reading.id)
        ).all()
    )
    reloaded_reading = api_seeded_session.get(Reading, reading.id)

    assert interpretation_count_after == interpretation_count_before
    assert reloaded_reading.status == ReadingStatus.INTERPRETED  # unchanged
    assert reloaded_reading.updated_at == reading_updated_at_before  # untouched


# --- 8: reinterpretation preserves history ----------------------------------------


def test_reinterpretation_creates_a_new_row_and_preserves_history(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    first = client.post(f"/readings/{reading.id}/interpret").json()
    second = client.post(f"/readings/{reading.id}/interpret").json()

    assert first["id"] != second["id"]

    history = client.get(f"/readings/{reading.id}/interpretations").json()
    assert [entry["id"] for entry in history] == [second["id"], first["id"]]

    api_seeded_session.expire_all()
    assert len(api_seeded_session.get(Reading, reading.id).interpretations) == 2


# --- 10: reinterpreting a SAVED reading preserves SAVED --------------------------


def test_reinterpreting_a_saved_reading_preserves_saved_status(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()
    client.post(f"/readings/{reading.id}/interpret")

    reading.status = ReadingStatus.SAVED
    api_seeded_session.commit()

    response = client.post(f"/readings/{reading.id}/interpret")
    assert response.status_code == 201

    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.SAVED  # never regressed
    assert len(reloaded.interpretations) == 2  # both runs preserved


# --- 11: incomplete reading -- documented error, engine never invoked, no row ---


def test_incomplete_reading_returns_409_engine_never_invoked_no_row_created(
    api_seeded_session, client, monkeypatch
):
    reading = _incomplete_reading(api_seeded_session)
    api_seeded_session.commit()

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("engine.interpret must not be called for an incomplete reading")

    monkeypatch.setattr(reading_orchestration, "interpret", _fail_if_called)

    response = client.post(f"/readings/{reading.id}/interpret")

    assert response.status_code == 409
    api_seeded_session.expire_all()
    reloaded = api_seeded_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.DRAFTING
    assert reloaded.interpretations == []


# --- 12: provenance / reference-data version survive the whole round trip -------


def test_provenance_and_reference_data_version_survive_the_full_round_trip(api_seeded_session, client):
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    posted = client.post(f"/readings/{reading.id}/interpret").json()
    current = client.get(f"/readings/{reading.id}/interpretations/current").json()
    narrative = client.get(f"/readings/{reading.id}/narrative").json()

    reference_data_version = posted["reference_data_version"]
    assert len(reference_data_version) == 64  # sha256 hex digest
    assert posted["interpretive_model"]["reference_data_version"] == reference_data_version
    assert current["reference_data_version"] == reference_data_version
    assert narrative["source_reference_data_version"] == reference_data_version

    real_draw_ids = {str(draw.id) for draw in reading.card_draws}
    citations = posted["interpretive_model"]["central_issue"]["citations"]
    assert citations
    for citation in citations:
        if citation["source_type"] == "card_draw":
            assert citation["card_draw_id"] in real_draw_ids


# --- 13: all four routes remain registered and functional ------------------------


def test_all_four_routes_are_registered_and_functional(api_seeded_session, client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "post" in paths["/readings/{reading_id}/interpret"]
    assert "get" in paths["/readings/{reading_id}/interpretations/current"]
    assert "get" in paths["/readings/{reading_id}/interpretations"]
    assert "get" in paths["/readings/{reading_id}/narrative"]

    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    assert client.post(f"/readings/{reading.id}/interpret").status_code == 201
    assert client.get(f"/readings/{reading.id}/interpretations/current").status_code == 200
    assert client.get(f"/readings/{reading.id}/interpretations").status_code == 200
    assert client.get(f"/readings/{reading.id}/narrative").status_code == 200


# --- No deferred rule (R3/R4) leaks into the output -------------------------------


def test_deferred_relationship_rules_cannot_leak_into_the_output(api_seeded_session, client, monkeypatch):
    """R3 (same-suit clustering) and R4 (Major Arcana density) are DEFERRED
    (Documentation/INTERPRETATION_RULES_DESIGN.md Section 7.1/12.3): the
    underlying evidence (relationships.evaluate_relationships) may be
    computed, but must never be used as an interpretive conclusion.

    engine.py's own pipeline (Stage 5, engine.py line ~153) calls
    evaluate_relationships() and discards its return value entirely --
    this test proves that discard is real, not incidental: even if
    evaluate_relationships() returned wildly different, obviously-poisoned
    data, the resulting InterpretiveModel served through the full API is
    byte-for-byte identical (aside from generated_at/row identity).
    """
    # Reinterpreting the SAME reading twice (rather than two separate
    # readings) means every card_draw_id cited is identical between runs
    # -- the only thing that should differ is whatever
    # evaluate_relationships() is allowed to influence, which must be
    # nothing.
    reading = _complete_reading(api_seeded_session)
    api_seeded_session.commit()

    baseline = client.post(f"/readings/{reading.id}/interpret").json()

    def _poisoned(_reading_context):
        return CardRelationships(
            same_suit_clusters=(SuitCluster(suit=Suit.CUPS, draws=()),) * 5,
            major_arcana_draws=(object(),) * 999,
        )

    monkeypatch.setattr(engine_module, "evaluate_relationships", _poisoned)

    poisoned = client.post(f"/readings/{reading.id}/interpret").json()

    for body in (baseline, poisoned):
        del body["id"], body["reading_id"], body["created_at"], body["sequence"]
        del body["interpretive_model"]["generated_at"]

    assert baseline == poisoned
