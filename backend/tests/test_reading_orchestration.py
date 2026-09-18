"""Tests for the Reading Integration orchestration layer (Step 9,
Documentation/READING_INTEGRATION_DESIGN.md): interpret_reading() and
get_narrative_for_reading().
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Interpretation, Orientation, Reading, ReadingStatus
from app.services import reading_orchestration
from app.services.reading_orchestration import (
    ReadingNotReadyForInterpretationError,
    get_narrative_for_reading,
    interpret_reading,
)
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


def _complete_reading(session) -> Reading:
    return build_reading(session, spread_name="Celtic Cross", draws=_FULL_CELTIC_CROSS_DRAWS)


def _incomplete_reading(session) -> Reading:
    # Only 2 of the Celtic Cross's 10 required positions are filled.
    return build_reading(
        session, spread_name="Celtic Cross",
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
        "generated_at": "2026-09-17T00:00:00Z",
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


# --- Reading.is_spread_complete ----------------------------------------------


def test_is_spread_complete_true_for_a_fully_drawn_spread(seeded_session):
    reading = _complete_reading(seeded_session)
    assert reading.is_spread_complete is True


def test_is_spread_complete_false_for_a_partially_drawn_spread(seeded_session):
    reading = _incomplete_reading(seeded_session)
    assert reading.is_spread_complete is False


# --- Precondition enforcement --------------------------------------------------


def test_incomplete_reading_is_rejected_before_the_engine_is_invoked(seeded_session, monkeypatch):
    reading = _incomplete_reading(seeded_session)

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("engine.interpret must not be called for an incomplete reading")

    monkeypatch.setattr(reading_orchestration, "interpret", _fail_if_called)

    with pytest.raises(ReadingNotReadyForInterpretationError):
        interpret_reading(seeded_session, reading)

    assert reading.interpretations == []
    assert reading.status == ReadingStatus.DRAFTING  # untouched


# --- Successful interpretation --------------------------------------------------


def test_complete_reading_is_interpreted_successfully(seeded_session):
    reading = _complete_reading(seeded_session)
    interpretation = interpret_reading(seeded_session, reading)

    assert isinstance(interpretation, Interpretation)
    assert interpretation.reading_id == reading.id


def test_a_new_interpretation_row_is_created(seeded_session):
    reading = _complete_reading(seeded_session)
    interpretation = interpret_reading(seeded_session, reading)

    fetched = seeded_session.get(Interpretation, interpretation.id)
    assert fetched is not None
    assert fetched.reading_id == reading.id


def test_multiple_interpretations_preserve_history(seeded_session):
    reading = _complete_reading(seeded_session)
    first = interpret_reading(seeded_session, reading)
    second = interpret_reading(seeded_session, reading)

    assert first.id != second.id
    assert len(reading.interpretations) == 2
    assert seeded_session.get(Interpretation, first.id) is not None
    assert seeded_session.get(Interpretation, second.id) is not None


# --- Sequence ordering ----------------------------------------------------------


def test_sequence_ordering_is_deterministic_across_reinterpretation(seeded_session):
    reading = _complete_reading(seeded_session)
    first = interpret_reading(seeded_session, reading)
    second = interpret_reading(seeded_session, reading)
    third = interpret_reading(seeded_session, reading)

    assert first.sequence < second.sequence < third.sequence
    assert [i.id for i in reading.interpretations] == [first.id, second.id, third.id]


def test_current_interpretation_is_the_highest_sequence_not_insertion_order(seeded_session):
    """Directly proves Resolved Q2: "current" is determined by `sequence`,
    not by created_at/insertion order. Row A is inserted first but given a
    HIGHER sequence than row B, inserted second -- current must be A.
    """
    reading = _complete_reading(seeded_session)

    row_a = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict("theme_a"), sequence=100,
    )
    seeded_session.add(row_a)
    seeded_session.flush()

    row_b = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict("theme_b"), sequence=1,
    )
    seeded_session.add(row_b)
    seeded_session.flush()

    current = seeded_session.execute(
        select(Interpretation)
        .where(Interpretation.reading_id == reading.id)
        .order_by(Interpretation.sequence.desc())
        .limit(1)
    ).scalar_one()

    assert current.id == row_a.id  # inserted first, but higher sequence


# --- Status transitions ----------------------------------------------------------


def test_drafting_transitions_to_interpreted(seeded_session):
    reading = _complete_reading(seeded_session)
    assert reading.status == ReadingStatus.DRAFTING
    interpret_reading(seeded_session, reading)
    assert reading.status == ReadingStatus.INTERPRETED


def test_spread_complete_transitions_to_interpreted(seeded_session):
    reading = _complete_reading(seeded_session)
    reading.status = ReadingStatus.SPREAD_COMPLETE
    seeded_session.flush()

    interpret_reading(seeded_session, reading)
    assert reading.status == ReadingStatus.INTERPRETED


def test_interpreted_stays_interpreted_on_reinterpretation(seeded_session):
    reading = _complete_reading(seeded_session)
    interpret_reading(seeded_session, reading)
    assert reading.status == ReadingStatus.INTERPRETED

    interpret_reading(seeded_session, reading)
    assert reading.status == ReadingStatus.INTERPRETED


def test_saved_reading_remains_saved_after_reinterpretation(seeded_session):
    reading = _complete_reading(seeded_session)
    interpret_reading(seeded_session, reading)
    reading.status = ReadingStatus.SAVED
    seeded_session.flush()

    interpretation_count_before = len(reading.interpretations)
    interpret_reading(seeded_session, reading)

    assert reading.status == ReadingStatus.SAVED  # never regressed
    assert len(reading.interpretations) == interpretation_count_before + 1  # new row still added


# --- Transaction boundaries -----------------------------------------------------


def test_interpret_reading_does_not_commit_the_session(seeded_session):
    """interpret_reading() must only flush, never commit -- the caller
    controls the transaction (Section 14). Rolling back after the call
    must undo the Interpretation row and the status change entirely.
    """
    reading = _complete_reading(seeded_session)
    reading_id = reading.id
    seeded_session.commit()  # commit reading creation so only the interpretation is rolled back

    interpret_reading(seeded_session, reading)
    assert reading.status == ReadingStatus.INTERPRETED

    seeded_session.rollback()

    reloaded = seeded_session.get(Reading, reading_id)
    assert reloaded.status == ReadingStatus.DRAFTING  # rolled back
    assert reloaded.interpretations == []  # rolled back


# --- Narrative retrieval ---------------------------------------------------------


def test_get_narrative_for_reading_uses_the_current_persisted_interpretation(seeded_session):
    reading = _complete_reading(seeded_session)

    stale = Interpretation(
        reading=reading, engine_version="0.1.0", reference_data_version="aaa",
        interpretive_model=_minimal_model_dict("stale_theme"), sequence=1,
    )
    seeded_session.add(stale)
    seeded_session.flush()

    current = Interpretation(
        reading=reading, engine_version="0.2.0", reference_data_version="bbb",
        interpretive_model=_minimal_model_dict("current_theme"), sequence=2,
    )
    seeded_session.add(current)
    seeded_session.flush()

    narrative = get_narrative_for_reading(seeded_session, reading)

    central_theme_section = next(s for s in narrative.sections if s.id == "central_theme")
    assert central_theme_section.statements[0].text == "Current Theme"


def test_get_narrative_for_reading_returns_none_when_never_interpreted(seeded_session):
    reading = _complete_reading(seeded_session)
    assert get_narrative_for_reading(seeded_session, reading) is None


def test_narrative_assembly_failure_does_not_alter_the_persisted_interpretation(
    seeded_session, monkeypatch
):
    reading = _complete_reading(seeded_session)
    interpretation = interpret_reading(seeded_session, reading)
    seeded_session.commit()

    def _boom(_model):
        raise RuntimeError("simulated narrative assembly failure")

    monkeypatch.setattr(reading_orchestration, "assemble_narrative", _boom)

    with pytest.raises(RuntimeError):
        get_narrative_for_reading(seeded_session, reading)

    # The already-committed Interpretation row and Reading status must be
    # completely unaffected by the narrative-assembly failure.
    seeded_session.expire_all()
    still_there = seeded_session.get(Interpretation, interpretation.id)
    assert still_there is not None
    reloaded_reading = seeded_session.get(Reading, reading.id)
    assert reloaded_reading.status == ReadingStatus.INTERPRETED


def test_get_narrative_for_reading_creates_no_new_rows_and_is_repeatable(seeded_session):
    """No NarrativeModel persistence: calling this twice must not add any
    new Interpretation rows (or anything else) -- it is a pure read +
    in-memory recompute each time.
    """
    reading = _complete_reading(seeded_session)
    interpret_reading(seeded_session, reading)
    seeded_session.commit()

    row_count_before = len(
        seeded_session.execute(
            select(Interpretation).where(Interpretation.reading_id == reading.id)
        ).all()
    )

    first = get_narrative_for_reading(seeded_session, reading)
    second = get_narrative_for_reading(seeded_session, reading)

    row_count_after = len(
        seeded_session.execute(
            select(Interpretation).where(Interpretation.reading_id == reading.id)
        ).all()
    )
    assert row_count_after == row_count_before
    assert first.model_dump(mode="json", exclude={"generated_at"}) == second.model_dump(
        mode="json", exclude={"generated_at"}
    )


# --- Provenance / reference-data version preservation ----------------------------


def test_provenance_and_reference_data_version_survive_the_full_lifecycle(seeded_session):
    reading = _complete_reading(seeded_session)
    interpretation = interpret_reading(seeded_session, reading)

    stored_model_json = interpretation.interpretive_model
    assert interpretation.engine_version == stored_model_json["engine_version"]
    assert interpretation.reference_data_version == stored_model_json["reference_data_version"]
    assert len(interpretation.reference_data_version) == 64  # sha256 hex digest

    narrative = get_narrative_for_reading(seeded_session, reading)
    assert narrative.source_engine_version == interpretation.engine_version
    assert narrative.source_reference_data_version == interpretation.reference_data_version
    assert narrative.source_schema_version == stored_model_json["schema_version"]

    # Citations are preserved end-to-end -- every card_draw citation in the
    # stored model corresponds to a real CardDraw on this reading.
    real_draw_ids = {str(d.id) for d in reading.card_draws}
    central_issue_citations = stored_model_json["central_issue"]["citations"]
    for citation in central_issue_citations:
        if citation["source_type"] == "card_draw":
            assert citation["card_draw_id"] in real_draw_ids
