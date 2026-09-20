"""Unit tests for the deterministic theme -> Scripture selection service
(app/services/scripture/selection.py), against hand-constructed
InterpretiveModel fixtures and directly-inserted ScriptureReference rows
-- independent of the real seeded reference-data content (except for one
explicit integration test at the bottom), so most of these tests remain
stable even if that seed content changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.models import Orientation, ScriptureReference
from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Explained,
    InterpretiveModel,
    Relationships,
    ThemeStrength,
)
from app.services.scripture.selection import _MAX_REFLECTIONS, select_scripture_reflections
from tests.interpretation_helpers import build_reading


def _citation(theme: str = "clarity", card_name: str = "Ace of Swords") -> Citation:
    return Citation(
        source_type="card_draw", card_draw_id=uuid4(), card_name=card_name,
        position_name="Situation", position_semantic_role="situation", contributing_theme=theme,
    )


def _model(theme_strength: tuple[ThemeStrength, ...] = (), **overrides) -> InterpretiveModel:
    central_theme = theme_strength[0].theme if theme_strength else "clarity"
    defaults: dict = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on?",
        spread_name="Single Card",
        card_interpretations=(
            CardInterpretation(
                position_name="The Card", semantic_role="general", position_order=1,
                card_name="Ace of Swords", orientation="upright",
                meaning_text="A breakthrough moment of mental clarity.",
                themes=("clarity",), citation=_citation(),
            ),
        ),
        relationships=Relationships(major_arcana_count=0, minor_arcana_count=1),
        theme_strength=theme_strength,
        central_issue=Explained(value=central_theme, citations=(_citation(central_theme),)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(
            value=f"Together, the drawn cards center on {central_theme}.", citations=(_citation(central_theme),)
        ),
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


def _reference(session, theme: str, **overrides) -> ScriptureReference:
    defaults = dict(
        theme=theme, book="Philippians", chapter=4, verse_start=6, verse_end=7,
        reference_display="Philippians 4:6-7", translation="KJV",
        context_note="A note about the passage.", reflection_connection="A connection to the theme.",
    )
    defaults.update(overrides)
    reference = ScriptureReference(**defaults)
    session.add(reference)
    session.flush()
    return reference


# --- Scripture enabled / deterministic mapping ----------------------------------


def test_returns_a_reflection_for_a_theme_with_an_approved_mapping(db_session):
    _reference(db_session, "anxiety")
    citations = (_citation("anxiety"),)
    model = _model(theme_strength=(ThemeStrength(theme="anxiety", count=2, citations=citations),))

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    reflection = perspective.reflections[0]
    assert reflection.theme == "anxiety"
    assert reflection.reference_display == "Philippians 4:6-7"
    assert reflection.book == "Philippians"
    assert reflection.translation == "KJV"
    assert reflection.theme_citations == citations


def test_selection_is_deterministic_for_identical_input(db_session):
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=3, citations=(_citation("hope"),)),))

    first = select_scripture_reflections(db_session, model)
    second = select_scripture_reflections(db_session, model)

    assert first.model_dump(mode="json", exclude={"generated_at"}) == second.model_dump(
        mode="json", exclude={"generated_at"}
    )


def test_a_theme_can_have_more_than_one_approved_reference(db_session):
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    _reference(
        db_session, "hope", book="Jeremiah", chapter=29, verse_start=11, verse_end=None,
        reference_display="Jeremiah 29:11",
    )
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 2
    assert {r.reference_display for r in perspective.reflections} == {"Romans 15:13", "Jeremiah 29:11"}


def test_respects_theme_strength_order_and_the_reflections_limit(db_session):
    for theme in ("hope", "grief", "fear", "patience"):
        _reference(
            db_session, theme, book="Psalms", chapter=1, verse_start=1,
            reference_display=f"Psalm 1:1 ({theme})",
        )
    theme_strength = tuple(
        ThemeStrength(theme=theme, count=count, citations=(_citation(theme),))
        for theme, count in [("hope", 4), ("grief", 3), ("fear", 2), ("patience", 1)]
    )
    model = _model(theme_strength=theme_strength)
    assert _MAX_REFLECTIONS == 3  # this test's own assumption, made explicit

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 3
    assert [r.theme for r in perspective.reflections] == ["hope", "grief", "fear"]


# --- No Scripture returned when no approved mapping exists ----------------------


def test_no_reflection_when_no_approved_mapping_exists_for_the_themes_present(db_session):
    model = _model(theme_strength=(ThemeStrength(theme="ambition", count=1, citations=(_citation("ambition"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


def test_only_themes_with_a_mapping_contribute_a_reflection(db_session):
    _reference(db_session, "hope")
    theme_strength = (
        ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),  # no mapping
        ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),  # mapped
    )
    model = _model(theme_strength=theme_strength)

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    assert perspective.reflections[0].theme == "hope"


def test_empty_theme_strength_produces_no_reflections(db_session):
    model = _model(theme_strength=())

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


# --- Scripture layer does not alter deterministic tarot interpretation ---------


def test_does_not_mutate_the_source_interpretive_model(db_session):
    _reference(db_session, "hope")
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))
    before = model.model_dump(mode="json")

    select_scripture_reflections(db_session, model)

    assert model.model_dump(mode="json") == before


def test_writes_no_rows_to_the_database(db_session):
    _reference(db_session, "hope")
    before_count = len(db_session.execute(select(ScriptureReference)).scalars().all())
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))

    select_scripture_reflections(db_session, model)

    after_count = len(db_session.execute(select(ScriptureReference)).scalars().all())
    assert after_count == before_count


# --- Guardrail disclaimer --------------------------------------------------------


def test_disclaimer_is_always_present_and_disclaims_divine_endorsement(db_session):
    # No ScriptureReference rows needed -- the disclaimer is attached
    # regardless of whether any reflection was found.
    model = _model(theme_strength=())

    perspective = select_scripture_reflections(db_session, model)

    assert "God's will" in perspective.disclaimer
    assert "not" in perspective.disclaimer.lower()


# --- Real end-to-end integration (real engine + real seeded scripture data) ----


def test_integration_with_the_real_engine_and_real_seeded_scripture_data(seeded_session):
    from app.services.interpretation.engine import interpret

    reading = build_reading(
        seeded_session, spread_name="Celtic Cross",
        draws=[
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
        ],
    )
    model = interpret(reading, seeded_session)

    perspective = select_scripture_reflections(seeded_session, model)

    themes_returned = {r.theme for r in perspective.reflections}
    theme_strength_tags = {t.theme for t in model.theme_strength}
    assert themes_returned  # this real fixture's own themes include at least one seeded mapping ("patience")
    assert themes_returned.issubset(theme_strength_tags)
    for reflection in perspective.reflections:
        assert len(reflection.theme_citations) >= 1
