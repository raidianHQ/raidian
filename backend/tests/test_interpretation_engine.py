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


# --- New synthesis fields: card_interpretations, relationships, theme_strength, ---
# --- deterministic_synthesis --------------------------------------------------------


def test_card_interpretations_has_one_entry_per_draw_ordered_by_position(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert len(model.card_interpretations) == len(CELTIC_CROSS_DRAWS)
    assert [c.position_order for c in model.card_interpretations] == sorted(
        c.position_order for c in model.card_interpretations
    )
    first = model.card_interpretations[0]
    assert first.position_name == "Situation"
    assert first.card_name == "Ace of Swords"
    assert first.orientation == "upright"
    assert first.meaning_text  # real seeded base_meaning_upright text, non-empty
    assert first.citation.card_name == "Ace of Swords"


def test_card_interpretation_themes_match_the_drawn_cards_own_themes(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    situation = next(c for c in model.card_interpretations if c.position_name == "Situation")
    # Ace of Swords contributing "clarity" is what fires the "Clarity vs.
    # Uncertainty" compound rule for this same fixture elsewhere in this
    # file (test_interpret_produces_a_fully_populated_model_for_a_rich_reading).
    assert "clarity" in situation.themes


def test_relationships_reports_major_arcana_density_for_the_celtic_cross_fixture(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert model.relationships.major_arcana_count == 9  # every draw except Ace of Swords
    assert model.relationships.minor_arcana_count == 1
    assert model.relationships.same_suit_clusters == ()  # only one Minor Arcana card drawn


def test_relationships_detects_a_same_suit_cluster_through_the_full_pipeline(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),
            ("Present Situation", "Two of Swords", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
        ],
    )
    model = interpret(reading, seeded_session)

    assert len(model.relationships.same_suit_clusters) == 1
    cluster = model.relationships.same_suit_clusters[0]
    assert cluster.suit == "swords"
    assert set(cluster.card_names) == {"Ace of Swords", "Two of Swords"}
    assert len(cluster.citations) == 2


def test_score_evidence_strength_signature_structurally_excludes_relationships():
    """R4 (Documentation/INTERPRETATION_RULES_DESIGN.md Section 7.1: Major
    Arcana density must never become an evidence-strength signal) is a
    structural guarantee, not just today's observed behavior:
    score_evidence_strength() doesn't even accept a relationships/
    CardRelationships parameter, so there is no argument through which
    `relationships` (now exposed on InterpretiveModel) could reach it by
    accident -- the same "structurally unreachable" proof style
    test_narrative_modules_contain_no_database_or_orm_references already
    uses for a different invariant.
    """
    import inspect

    from app.services.interpretation.evidence import score_evidence_strength

    params = set(inspect.signature(score_evidence_strength).parameters)
    assert "relationships" not in params
    assert "card_relationships" not in params


def test_derive_supporting_themes_signature_structurally_excludes_relationships():
    """The same structural guarantee as above, for R3 (same-suit
    clustering must never become a supporting_themes entry):
    engine._derive_supporting_themes() doesn't accept a relationships/
    CardRelationships parameter either.
    """
    import inspect

    from app.services.interpretation.engine import _derive_supporting_themes

    params = set(inspect.signature(_derive_supporting_themes).parameters)
    assert "relationships" not in params
    assert "card_relationships" not in params


def test_relationships_differs_between_readings_with_different_compositions(seeded_session):
    """Sanity check the other direction: `relationships` is genuinely
    wired to each Reading's own evidence, not a constant.
    """
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    clustered_reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),
            ("Present Situation", "Two of Swords", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
        ],
    )
    clustered_model = interpret(clustered_reading, seeded_session)

    assert model.relationships != clustered_model.relationships


def test_theme_strength_is_the_full_ranked_list_with_counts(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert len(model.theme_strength) >= len(model.supporting_themes) + 1  # central_issue + supporting, at least
    counts = [t.count for t in model.theme_strength]
    assert counts == sorted(counts, reverse=True)
    assert model.theme_strength[0].theme == model.central_issue.value
    assert model.theme_strength[0].count >= 1
    for entry in model.theme_strength:
        assert len(entry.citations) == entry.count


def test_theme_strength_entries_with_count_2_or_more_are_reinforced_themes(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    reinforced = [t for t in model.theme_strength if t.count >= 2]
    assert len(reinforced) >= 1  # the rich Celtic Cross fixture has real overlap


def test_spread_name_and_description_are_populated(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert model.spread_name == "Celtic Cross"
    assert model.spread_description == reading.spread.description


def test_deterministic_synthesis_is_always_present_with_citations(seeded_session):
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    assert model.deterministic_synthesis.value.startswith("Together, ")
    assert model.central_issue.value in model.deterministic_synthesis.value
    assert len(model.deterministic_synthesis.citations) >= 1


def test_deterministic_synthesis_mentions_tension_trajectory_blocker_and_advice_when_present(seeded_session):
    """The rich Celtic Cross fixture produces a tension, a trajectory, a
    blocker, and advice (test_interpret_produces_a_fully_populated_model_
    for_a_rich_reading above already confirms each field individually) --
    the synthesis sentence must reference all of them, not just the
    central issue.
    """
    reading = _rich_reading(seeded_session)
    model = interpret(reading, seeded_session)

    text = model.deterministic_synthesis.value
    assert model.primary_tension.value.label in text
    assert model.trajectory.value.arc[0].card_name in text
    assert model.trajectory.value.arc[-1].card_name in text
    assert model.blocker.value in text
    assert model.advice.value in text


def test_deterministic_synthesis_omits_tension_clause_when_no_tension_fires(seeded_session):
    thin_reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
    )
    model = interpret(thin_reading, seeded_session)

    assert model.primary_tension is None
    assert "held in tension as" not in model.deterministic_synthesis.value


def test_deterministic_synthesis_is_deterministic_for_identical_input(seeded_session):
    reading = _rich_reading(seeded_session)
    first = interpret(reading, seeded_session)
    second = interpret(reading, seeded_session)
    assert first.deterministic_synthesis == second.deterministic_synthesis


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
