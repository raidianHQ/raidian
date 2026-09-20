"""Unit tests for app/services/ai_narrative/context.py -- deliberately
trivial, matching how trivial build_deterministic_reading_context() itself
is (see that module's own docstring for why).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Explained,
    InterpretiveModel,
    Relationships,
)
from app.schemas.scripture_model import ScripturalPerspective, ScriptureReflection
from app.services.ai_narrative.context import build_deterministic_reading_context


def _citation() -> Citation:
    return Citation(
        source_type="card_draw", card_draw_id=uuid4(), card_name="Ace of Swords",
        position_name="Situation", position_semantic_role="situation", contributing_theme="clarity",
    )


def _model() -> InterpretiveModel:
    return InterpretiveModel(
        schema_version="1.0", engine_version="0.1.0-foundation", reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc), central_question="What should I focus on?",
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
        central_issue=Explained(value="clarity", citations=(_citation(),)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(value="Clarity is the focus.", citations=(_citation(),)),
    )


def _scripture() -> ScripturalPerspective:
    reflection = ScriptureReflection(
        theme="patience", book="James", chapter=1, verse_start=2, verse_end=4,
        reference_display="James 1:2-4", translation="KJV",
        context_note="A note.", reflection_connection="A connection.",
        theme_citations=(_citation(),),
    )
    return ScripturalPerspective(
        schema_version="1.0", generated_at=datetime.now(timezone.utc),
        source_schema_version="1.0", reflections=(reflection,),
    )


def test_context_wraps_the_interpretive_model_and_omits_scripture_by_default():
    model = _model()

    context = build_deterministic_reading_context(model, None)

    assert context.interpretation == model
    assert context.scripture is None


def test_context_carries_the_supplied_scripture_when_provided():
    model = _model()
    scripture = _scripture()

    context = build_deterministic_reading_context(model, scripture)

    assert context.scripture == scripture
    assert context.scripture.reflections[0].theme == "patience"
