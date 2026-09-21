"""Unit tests for app/services/scriptural_reflection/persistence.py --
mirrors tests/test_ai_narrative_persistence.py's own structure exactly,
applied to the deterministic Scripture layer instead of the AI Narrative
layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Orientation, ScripturalReflection
from app.schemas.scripture_model import ScripturalPerspective, ScriptureReflection
from app.services.interpretation.engine import interpret
from app.services.interpretation.persistence import save_interpretation
from app.services.scriptural_reflection.persistence import (
    get_current_scriptural_reflection,
    save_scriptural_reflection,
)
from tests.interpretation_helpers import build_reading


def _citation() -> dict:
    return {
        "source_type": "card_draw",
        "card_draw_id": None,
        "card_name": "Nine of Swords",
        "position_name": "The Card",
        "position_semantic_role": "general",
        "contributing_theme": "fear",
        "rule_id": None,
        "rule_tier": None,
    }


def _perspective(**overrides) -> ScripturalPerspective:
    reflections = overrides.pop("reflections", None)
    if reflections is None:
        reflections = (
            ScriptureReflection(
                theme="fear", book="2 Timothy", chapter=1, verse_start=7, verse_end=None,
                reference_display="2 Timothy 1:7", translation="KJV",
                context_note="A note.", reflection_connection="A connection.",
                theme_citations=(_citation(),),
            ),
        )
    defaults: dict = dict(
        schema_version="1.0", generated_at=datetime.now(timezone.utc),
        source_schema_version="1.0", reflections=reflections,
    )
    defaults.update(overrides)
    return ScripturalPerspective(**defaults)


def _interpretation(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Nine of Swords", Orientation.UPRIGHT)],
    )
    model = interpret(reading, seeded_session)
    return save_interpretation(seeded_session, reading, model)


def test_save_scriptural_reflection_creates_a_row_tied_to_the_interpretation(seeded_session):
    interpretation = _interpretation(seeded_session)
    perspective = _perspective()

    row = save_scriptural_reflection(seeded_session, interpretation, perspective)

    assert row.interpretation_id == interpretation.id
    assert row.scriptural_perspective["reflections"][0]["theme"] == "fear"


def test_save_scriptural_reflection_assigns_increasing_sequence_and_keeps_history(seeded_session):
    interpretation = _interpretation(seeded_session)

    first = save_scriptural_reflection(seeded_session, interpretation, _perspective())
    second = save_scriptural_reflection(
        seeded_session, interpretation,
        _perspective(
            reflections=(
                ScriptureReflection(
                    theme="anxiety", book="Philippians", chapter=4, verse_start=6, verse_end=7,
                    reference_display="Philippians 4:6-7", translation="KJV",
                    context_note="A note.", reflection_connection="A connection.",
                    theme_citations=(_citation(),),
                ),
            ),
        ),
    )

    assert second.sequence > first.sequence
    rows = seeded_session.execute(
        select(ScripturalReflection).where(ScripturalReflection.interpretation_id == interpretation.id)
    ).scalars().all()
    assert len(rows) == 2


def test_save_scriptural_reflection_round_trips_through_json(seeded_session):
    interpretation = _interpretation(seeded_session)
    perspective = _perspective()

    row = save_scriptural_reflection(seeded_session, interpretation, perspective)
    seeded_session.flush()
    seeded_session.expire(row)

    reloaded = ScripturalPerspective.model_validate(row.scriptural_perspective)
    assert reloaded == perspective


def test_get_current_scriptural_reflection_returns_none_when_never_saved(seeded_session):
    interpretation = _interpretation(seeded_session)

    assert get_current_scriptural_reflection(seeded_session, interpretation) is None


def test_get_current_scriptural_reflection_returns_the_highest_sequence_row(seeded_session):
    interpretation = _interpretation(seeded_session)
    save_scriptural_reflection(seeded_session, interpretation, _perspective())
    second = save_scriptural_reflection(
        seeded_session, interpretation,
        _perspective(
            reflections=(
                ScriptureReflection(
                    theme="anxiety", book="Philippians", chapter=4, verse_start=6, verse_end=7,
                    reference_display="Philippians 4:6-7", translation="KJV",
                    context_note="A note.", reflection_connection="A connection.",
                    theme_citations=(_citation(),),
                ),
            ),
        ),
    )

    current = get_current_scriptural_reflection(seeded_session, interpretation)

    assert current is not None
    assert current.id == second.id
