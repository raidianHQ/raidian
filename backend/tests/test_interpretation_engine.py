"""Integration tests for the full pipeline orchestrator (engine.interpret)
and persistence (persistence.save_interpretation).

The central requirement under test throughout this file: identical inputs
(same Reading evidence + same reference-data content) must produce
structurally identical InterpretiveModel output every time
(INTERPRETATION_ENGINE_DESIGN.md Section 5).
"""

import pytest

from app.models import Interpretation, Orientation, ReadingStatus
from app.services.interpretation.engine import ENGINE_VERSION, SCHEMA_VERSION, interpret
from app.services.interpretation.persistence import save_interpretation
from tests.interpretation_helpers import build_reading

CELTIC_CROSS_DRAWS = [
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


def _rich_reading(session):
    return build_reading(session, spread_name="Celtic Cross", draws=CELTIC_CROSS_DRAWS)


def test_interpret_raises_on_a_reading_with_no_card_draws(seeded_session):
    from app.models import Deck, ReflectionSession, Spread, Reading
    from sqlalchemy import select

    deck = seeded_session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()
    spread = seeded_session.scalars(select(Spread).where(Spread.name == "Single Card")).one()
    rs = ReflectionSession()
    seeded_session.add(rs)
    seeded_session.flush()
    reading = Reading(reflection_session=rs, spread=spread, deck=deck, question="Nothing drawn yet")
    seeded_session.add(reading)
    seeded_session.flush()

    with pytest.raises(ValueError):
        interpret(reading, seeded_session)


def test_interpret_produces_a_fully_populated_model_for_a_rich_reading(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert model.schema_version == SCHEMA_VERSION
    assert model.engine_version == ENGINE_VERSION
    assert len(model.reference_data_version) == 64
    assert model.central_question == reading.question
    assert model.central_issue is not None
    assert model.primary_tension is not None
    assert model.primary_tension.value.label == "Clarity vs. Uncertainty"
    assert model.trajectory is not None
    assert model.blocker is not None
    assert model.advice is not None
    assert model.clarification is not None
    assert model.evidence_strength == "strong"
    assert model.uncertainty == ()


def test_interpret_is_deterministic_for_identical_input(seeded_session):
    """The core determinism requirement: running interpret() twice against
    the same Reading + same reference data produces structurally identical
    output (ignoring only the generated_at timestamp, which is explicitly
    metadata about the run, never an input -- Section 4.1).
    """
    reading = _rich_reading(seeded_session)

    first = interpret(reading, seeded_session)
    second = interpret(reading, seeded_session)

    assert first.model_dump(mode="json", exclude={"generated_at"}) == second.model_dump(
        mode="json", exclude={"generated_at"}
    )


def _strip_row_identity(value):
    """Recursively drops card_draw_id (a real, and correctly *different*,
    row UUID per Reading) so two independently-built Readings with
    identical card/position content can be compared on content alone.
    """
    if isinstance(value, dict):
        return {k: _strip_row_identity(v) for k, v in value.items() if k != "card_draw_id"}
    if isinstance(value, list):
        return [_strip_row_identity(v) for v in value]
    return value


def test_interpret_is_deterministic_across_independently_built_readings_with_identical_evidence(
    seeded_session,
):
    """Two different Readings (different reflection sessions, different
    row IDs) but with the same question, spread, and drawn cards must
    produce the same interpretation *content* -- proving determinism is
    about content, not row identity. Citations legitimately still point at
    each Reading's own distinct card_draw_id (that's the point of a
    citation), so identity fields are stripped before comparing here; the
    stricter same-Reading-called-twice case above already covers exact
    citation equality.
    """
    reading_a = build_reading(seeded_session, spread_name="Celtic Cross", draws=CELTIC_CROSS_DRAWS)
    reading_b = build_reading(seeded_session, spread_name="Celtic Cross", draws=CELTIC_CROSS_DRAWS)

    model_a = interpret(reading_a, seeded_session)
    model_b = interpret(reading_b, seeded_session)

    fields_to_compare = {
        "central_issue", "primary_tension", "supporting_themes", "trajectory",
        "blocker", "uncertainty", "advice", "clarification", "contradictions",
        "evidence_strength", "reference_data_version",
    }
    dump_a = _strip_row_identity(model_a.model_dump(mode="json", include=fields_to_compare))
    dump_b = _strip_row_identity(model_b.model_dump(mode="json", include=fields_to_compare))
    assert dump_a == dump_b


def test_interpret_differs_for_a_thin_reading_vs_a_rich_one(seeded_session):
    """Sanity check the other direction: determinism doesn't mean the
    engine always outputs the same thing -- different evidence must
    produce different conclusions.
    """
    rich = interpret(_rich_reading(seeded_session), seeded_session)

    thin_reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
    )
    thin = interpret(thin_reading, seeded_session)

    assert rich.evidence_strength != thin.evidence_strength
    assert rich.uncertainty != thin.uncertainty


def test_uncertainty_is_always_present_as_a_field_even_when_empty(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)
    assert isinstance(model.uncertainty, tuple)  # required field, never omitted


def test_every_explained_field_carries_at_least_one_citation(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert len(model.central_issue.citations) >= 1
    for explained in (model.primary_tension, model.trajectory, model.blocker, model.advice, model.clarification):
        if explained is not None:
            assert len(explained.citations) >= 1
    for supporting in model.supporting_themes:
        assert len(supporting.citations) >= 1


# --- Persistence ----------------------------------------------------------


def test_save_interpretation_creates_a_row_and_updates_reading_status(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    interpretation = save_interpretation(seeded_session, reading, model)
    seeded_session.commit()

    assert interpretation.reading_id == reading.id
    assert interpretation.engine_version == model.engine_version
    assert interpretation.reference_data_version == model.reference_data_version
    assert reading.status == ReadingStatus.INTERPRETED


def test_save_interpretation_round_trips_the_model_through_json(seeded_session):
    from app.schemas.interpretive_model import InterpretiveModel

    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)
    interpretation = save_interpretation(seeded_session, reading, model)
    seeded_session.commit()

    seeded_session.expire_all()
    reloaded = seeded_session.get(Interpretation, interpretation.id)
    restored_model = InterpretiveModel.model_validate(reloaded.interpretive_model)

    assert restored_model.model_dump(mode="json") == model.model_dump(mode="json")


def test_reinterpreting_preserves_the_prior_interpretation(seeded_session):
    """Reinterpretation must never destroy Reading evidence or a prior
    Interpretation -- RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 17.
    """
    reading = _rich_reading(seeded_session)
    original_draw_ids = {d.id for d in reading.card_draws}

    model_1 = interpret(reading, seeded_session)
    interpretation_1 = save_interpretation(seeded_session, reading, model_1)
    seeded_session.commit()

    model_2 = interpret(reading, seeded_session)  # simulates re-running (e.g. a newer engine)
    interpretation_2 = save_interpretation(seeded_session, reading, model_2)
    seeded_session.commit()

    assert interpretation_1.id != interpretation_2.id
    assert len(reading.interpretations) == 2
    assert {d.id for d in reading.card_draws} == original_draw_ids  # evidence untouched
