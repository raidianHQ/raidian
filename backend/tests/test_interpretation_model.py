"""DB-level tests for the Interpretation model itself -- relationships,
cascade behavior, history preservation. See
Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1.
"""

from app.models import Interpretation, Reading, ReadingStatus
from tests.factories import make_deck, make_reading, make_spread


def _minimal_model_dict() -> dict:
    return {
        "schema_version": "1.0",
        "engine_version": "0.1.0-foundation",
        "reference_data_version": "deadbeef",
        "generated_at": "2026-09-17T00:00:00Z",
        "central_question": "What should I focus on?",
        "central_issue": {"value": "new_beginnings", "citations": [{"source_type": "card_draw"}]},
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


def test_interpretation_can_be_created_for_a_reading(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    interpretation = Interpretation(
        reading=reading,
        engine_version="0.1.0-foundation",
        reference_data_version="deadbeef",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(interpretation)
    db_session.flush()

    assert interpretation.id is not None
    assert interpretation.reading_id == reading.id
    assert interpretation.created_at is not None


def test_reading_status_accepts_interpreted(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    reading.status = ReadingStatus.INTERPRETED
    db_session.flush()

    reloaded = db_session.get(Reading, reading.id)
    assert reloaded.status == ReadingStatus.INTERPRETED


def test_a_reading_can_have_multiple_interpretations_over_time(db_session):
    """Reinterpretation must not destroy or overwrite a prior
    Interpretation row -- history is preserved by the one-to-many shape
    itself (INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1).
    """
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    first = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(first)
    db_session.flush()

    second = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(second)
    db_session.flush()

    assert len(reading.interpretations) == 2
    assert db_session.get(Interpretation, first.id) is not None
    assert db_session.get(Interpretation, second.id) is not None


def test_current_interpretation_is_the_most_recently_created(db_session):
    """No is_current flag -- "current" is defined as latest created_at
    (INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1)."""
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    first = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(first)
    db_session.flush()
    second = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(second)
    db_session.flush()

    # relationship is ordered by created_at (model definition) -- the most
    # recent should be last.
    assert reading.interpretations[-1].id == second.id


def test_deleting_a_reading_cascades_to_its_interpretations(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    interpretation = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict(),
    )
    db_session.add(interpretation)
    db_session.flush()
    interpretation_id = interpretation.id

    db_session.delete(reading)
    db_session.flush()

    assert db_session.get(Interpretation, interpretation_id) is None


def test_interpretive_model_json_round_trips_through_the_database(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    payload = _minimal_model_dict()

    interpretation = Interpretation(
        reading=reading, engine_version="0.1.0-foundation", reference_data_version="deadbeef",
        interpretive_model=payload,
    )
    db_session.add(interpretation)
    db_session.commit()

    db_session.expire_all()
    reloaded = db_session.get(Interpretation, interpretation.id)
    assert reloaded.interpretive_model == payload
