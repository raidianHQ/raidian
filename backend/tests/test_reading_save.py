"""Tests for the Save Reading behavior implemented in Step 18
(Documentation/SAVE_READING_DESIGN.md Section 5/6): Reading.mark_saved()
-- a pure user-curation/retention marker with no effect on Interpretation,
Narrative, or CardDraw.

Uses tests/factories.py's minimal placeholder builders (not the real
seeded reference data) for every test except the last, which needs a real
Interpretation to confirm compatibility with the already-approved
reinterpretation-after-SAVED behavior (Step 9) -- exactly matching
test_reading_lifecycle.py's own established convention for this project.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import CardDraw, Interpretation, Orientation, Reading, ReadingStatus
from app.models.exceptions import ReadingNotSaveableError
from app.services.reading_orchestration import interpret_reading
from tests.factories import make_deck, make_major_card, make_reading, make_spread
from tests.interpretation_helpers import build_reading


def _setup_three_position_reading(db_session):
    spread = make_spread(db_session, name="Three Card", position_names=("Past", "Present", "Future"))
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    return reading, spread, deck


def _complete_three_position_reading(db_session):
    """Builds and returns a reading already at SPREAD_COMPLETE."""
    reading, spread, deck = _setup_three_position_reading(db_session)
    cards = [make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(3)]
    for order, (position, card) in enumerate(zip(spread.positions, cards), start=1):
        reading.add_card_draw(
            position=position, card=card, orientation=Orientation.UPRIGHT, draw_order=order
        )
    db_session.flush()
    assert reading.status == ReadingStatus.SPREAD_COMPLETE
    return reading, spread, deck


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


# --- Allowed transitions ----------------------------------------------------------


def test_drafting_raises_reading_not_saveable_error(db_session):
    reading, _spread, _deck = _setup_three_position_reading(db_session)
    assert reading.status == ReadingStatus.DRAFTING

    with pytest.raises(ReadingNotSaveableError):
        reading.mark_saved()

    assert reading.status == ReadingStatus.DRAFTING  # unchanged


def test_spread_complete_becomes_saved(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)

    reading.mark_saved()

    assert reading.status == ReadingStatus.SAVED


def test_interpreted_becomes_saved(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    reading.status = ReadingStatus.INTERPRETED
    db_session.flush()

    reading.mark_saved()

    assert reading.status == ReadingStatus.SAVED


def test_saved_is_idempotent(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    reading.mark_saved()
    assert reading.status == ReadingStatus.SAVED

    reading.mark_saved()  # calling it again must not raise or change anything

    assert reading.status == ReadingStatus.SAVED


# --- Explicit edge case: no Interpretation required -------------------------------


def test_spread_complete_with_zero_interpretations_can_be_saved(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    assert reading.interpretations == []

    reading.mark_saved()

    assert reading.status == ReadingStatus.SAVED
    assert reading.interpretations == []  # still zero -- saving never required one


# --- No side effects on other data --------------------------------------------------


def test_saving_creates_no_new_database_rows(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    db_session.commit()

    def _counts():
        return {
            "readings": db_session.execute(select(func.count()).select_from(Reading)).scalar(),
            "card_draws": db_session.execute(select(func.count()).select_from(CardDraw)).scalar(),
            "interpretations": db_session.execute(select(func.count()).select_from(Interpretation)).scalar(),
        }

    before = _counts()
    reading.mark_saved()
    db_session.flush()
    after = _counts()

    assert after == before


def test_saving_does_not_modify_existing_interpretation_rows(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    interpretation = Interpretation(
        reading=reading, engine_version="0.1.0-foundation", reference_data_version="deadbeef",
        interpretive_model=_minimal_model_dict(), sequence=1,
    )
    db_session.add(interpretation)
    db_session.commit()
    interpretation_id = interpretation.id
    stored_model_before = dict(interpretation.interpretive_model)

    reading.mark_saved()
    db_session.commit()

    db_session.expire_all()
    reloaded = db_session.get(Interpretation, interpretation_id)
    assert reloaded.interpretive_model == stored_model_before
    assert reloaded.sequence == 1
    assert reloaded.engine_version == "0.1.0-foundation"


def test_saving_does_not_modify_card_draws(db_session):
    reading, spread, _deck = _complete_three_position_reading(db_session)
    before = [
        (d.id, d.position_id, d.card_id, d.orientation, d.draw_order)
        for d in sorted(reading.card_draws, key=lambda d: d.draw_order)
    ]

    reading.mark_saved()
    db_session.flush()

    after = [
        (d.id, d.position_id, d.card_id, d.orientation, d.draw_order)
        for d in sorted(reading.card_draws, key=lambda d: d.draw_order)
    ]
    assert after == before


def test_saving_does_not_alter_unrelated_reading_fields(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    question_before = reading.question
    question_domain_before = reading.question_domain
    draw_method_before = reading.draw_method
    spread_id_before = reading.spread_id
    deck_id_before = reading.deck_id
    created_at_before = reading.created_at

    reading.mark_saved()

    assert reading.question == question_before
    assert reading.question_domain == question_domain_before
    assert reading.draw_method == draw_method_before
    assert reading.spread_id == spread_id_before
    assert reading.deck_id == deck_id_before
    assert reading.created_at == created_at_before
    assert reading.status == ReadingStatus.SAVED  # the only field that changed


# --- Transaction behavior -----------------------------------------------------------


def test_commit_persists_saved(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    reading_id = reading.id

    reading.mark_saved()
    db_session.commit()

    db_session.expire_all()
    reloaded = db_session.get(Reading, reading_id)
    assert reloaded.status == ReadingStatus.SAVED


def test_rollback_restores_previous_status(db_session):
    reading, _spread, _deck = _complete_three_position_reading(db_session)
    db_session.commit()  # commit at SPREAD_COMPLETE
    reading_id = reading.id

    reading.mark_saved()
    assert reading.status == ReadingStatus.SAVED  # in-memory, not yet committed

    db_session.rollback()

    reloaded = db_session.get(Reading, reading_id)
    assert reloaded.status == ReadingStatus.SPREAD_COMPLETE  # rolled back


# --- Compatibility with Step 9 reinterpretation behavior ---------------------------


def test_reinterpretation_after_mark_saved_preserves_saved_and_creates_new_interpretation(seeded_session):
    """Uses the real seeded reference data and the actual Interpretation
    Engine (via interpret_reading()) to confirm Reading.mark_saved()
    composes correctly with the already-approved, already-tested
    reinterpretation-after-SAVED behavior (Step 9) -- not merely that a
    manually-set SAVED status is preserved (already covered elsewhere),
    but that reaching SAVED through this new method specifically works.
    """
    reading = build_reading(
        seeded_session,
        spread_name="Three Card",
        draws=[
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Present Situation", "The Magician", Orientation.UPRIGHT),
            ("Near Future", "The Star", Orientation.UPRIGHT),
        ],
    )
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    first = interpret_reading(seeded_session, reading)
    reading.mark_saved()
    seeded_session.commit()
    assert reading.status == ReadingStatus.SAVED

    second = interpret_reading(seeded_session, reading)

    assert reading.status == ReadingStatus.SAVED  # preserved, never regressed
    assert second.id != first.id
    assert len(reading.interpretations) == 2  # history preserved
