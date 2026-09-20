"""Integration tests for the full narrative assembly orchestrator
(assembler.assemble_narrative), plus the architectural guarantees
NARRATIVE_LAYER_DESIGN.md requires: no database/external dependency, full
determinism, and correct narrative_template_version stamping.
"""

from __future__ import annotations

import inspect

from app.models import Orientation
from app.services.interpretation.engine import interpret
from app.services.narrative import assembler, humanize, sections
from app.services.narrative.assembler import (
    NARRATIVE_TEMPLATE_VERSION,
    SCHEMA_VERSION,
    assemble_narrative,
)
from tests.interpretation_helpers import build_reading

_RICH_DRAWS = [
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

_SECTION_ORDER = (
    "your_reading",
    "central_theme",
    "the_tension",
    "what_stands_in_the_way",
    "what_the_spread_shows",
    "where_things_appear_to_be_moving",
    "what_may_be_unclear",
    "advice",
    "clarification",
    "overall_reflection",
)


def _rich_model(session):
    reading = build_reading(session, spread_name="Celtic Cross", draws=_RICH_DRAWS)
    return interpret(reading, session)


def _thin_model(session):
    reading = build_reading(
        session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
    )
    return interpret(reading, session)


# --- Structural / ordering guarantees ----------------------------------------


def test_all_ten_sections_always_present_in_fixed_order(seeded_session):
    model = _rich_model(seeded_session)
    narrative = assemble_narrative(model)
    assert [s.id for s in narrative.sections] == list(_SECTION_ORDER)
    assert len(narrative.sections) == 10


def test_thin_reading_still_produces_all_ten_sections_some_marked_absent(seeded_session):
    model = _thin_model(seeded_session)
    narrative = assemble_narrative(model)
    assert [s.id for s in narrative.sections] == list(_SECTION_ORDER)
    presence = {s.id: s.present for s in narrative.sections}
    # A Single Card reading has no tension/blocker/trajectory/advice/clarification.
    assert presence["the_tension"] is False
    assert presence["what_stands_in_the_way"] is False
    assert presence["where_things_appear_to_be_moving"] is False
    assert presence["advice"] is False
    assert presence["clarification"] is False
    # Always-present sections remain present even on a thin reading.
    assert presence["your_reading"] is True
    assert presence["central_theme"] is True
    assert presence["what_may_be_unclear"] is True
    assert presence["overall_reflection"] is True


# --- Version stamping ---------------------------------------------------------


def test_narrative_template_version_and_schema_version_are_stamped(seeded_session):
    model = _rich_model(seeded_session)
    narrative = assemble_narrative(model)
    assert narrative.schema_version == SCHEMA_VERSION
    assert narrative.narrative_template_version == NARRATIVE_TEMPLATE_VERSION
    assert narrative.narrative_template_version  # non-empty


def test_source_versions_are_copied_verbatim_from_the_interpretive_model(seeded_session):
    model = _rich_model(seeded_session)
    narrative = assemble_narrative(model)
    assert narrative.source_schema_version == model.schema_version
    assert narrative.source_engine_version == model.engine_version
    assert narrative.source_reference_data_version == model.reference_data_version


# --- Determinism ---------------------------------------------------------------


def test_assemble_narrative_is_deterministic_for_identical_input(seeded_session):
    model = _rich_model(seeded_session)
    first = assemble_narrative(model)
    second = assemble_narrative(model)
    assert first.model_dump(mode="json", exclude={"generated_at"}) == second.model_dump(
        mode="json", exclude={"generated_at"}
    )


def test_assemble_narrative_is_deterministic_across_independently_built_identical_readings(
    seeded_session,
):
    reading_a = build_reading(seeded_session, spread_name="Celtic Cross", draws=_RICH_DRAWS)
    reading_b = build_reading(seeded_session, spread_name="Celtic Cross", draws=_RICH_DRAWS)
    model_a = interpret(reading_a, seeded_session)
    model_b = interpret(reading_b, seeded_session)

    narrative_a = assemble_narrative(model_a)
    narrative_b = assemble_narrative(model_b)

    # Strip card_draw_id (legitimately different per-Reading row identity,
    # same pattern test_interpretation_engine.py already uses) before
    # comparing narrative text/structure content.
    def _strip(value):
        if isinstance(value, dict):
            return {k: _strip(v) for k, v in value.items() if k != "card_draw_id"}
        if isinstance(value, list):
            return [_strip(v) for v in value]
        return value

    dump_a = _strip(narrative_a.model_dump(mode="json", exclude={"generated_at"}))
    dump_b = _strip(narrative_b.model_dump(mode="json", exclude={"generated_at"}))
    assert dump_a == dump_b


# --- Citation preservation ------------------------------------------------------


def test_central_theme_citations_are_identical_to_the_source_interpretive_model(seeded_session):
    model = _rich_model(seeded_session)
    narrative = assemble_narrative(model)
    central_theme_section = next(s for s in narrative.sections if s.id == "central_theme")
    assert central_theme_section.statements[0].citations == model.central_issue.citations


def test_the_tension_citations_are_identical_to_the_source_when_present(seeded_session):
    model = _rich_model(seeded_session)
    assert model.primary_tension is not None  # this fixture is known to fire a compound rule
    narrative = assemble_narrative(model)
    tension_section = next(s for s in narrative.sections if s.id == "the_tension")
    assert tension_section.statements[0].citations == model.primary_tension.citations


def test_no_narrative_statement_introduces_a_citation_absent_from_the_source_model(seeded_session):
    """Every citation appearing anywhere in the NarrativeModel must trace
    back to a citation already present somewhere in the source
    InterpretiveModel -- the concrete, checkable form of "no new claims."
    """
    model = _rich_model(seeded_session)
    narrative = assemble_narrative(model)

    source_citations: set[tuple] = set()
    if model.central_issue:
        source_citations.update(c.model_dump_json() for c in model.central_issue.citations)
    if model.primary_tension:
        source_citations.update(c.model_dump_json() for c in model.primary_tension.citations)
    for entry in model.supporting_themes:
        source_citations.update(c.model_dump_json() for c in entry.citations)
    if model.trajectory:
        source_citations.update(c.model_dump_json() for c in model.trajectory.citations)
    if model.blocker:
        source_citations.update(c.model_dump_json() for c in model.blocker.citations)
    if model.advice:
        source_citations.update(c.model_dump_json() for c in model.advice.citations)
    if model.clarification:
        source_citations.update(c.model_dump_json() for c in model.clarification.citations)
    for contradiction in model.contradictions:
        source_citations.update(c.model_dump_json() for c in contradiction.sources)

    for section in narrative.sections:
        for statement in section.statements:
            for citation in statement.citations:
                assert citation.model_dump_json() in source_citations


# --- No database / external dependency ------------------------------------------


def test_assemble_narrative_accepts_a_hand_built_model_with_no_database_at_all():
    """The strongest possible proof of "pure downstream transformation":
    build an InterpretiveModel directly (no session, no seed, no fixture
    helpers) and confirm the assembler works on it unmodified.
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.schemas.interpretive_model import (
        CardInterpretation,
        Citation,
        Explained,
        InterpretiveModel,
        Relationships,
    )

    citation = Citation(
        source_type="card_draw", card_draw_id=uuid4(), card_name="The Fool",
        position_name="The Card", position_semantic_role="general",
        contributing_theme="new_beginnings",
    )
    model = InterpretiveModel(
        schema_version="1.0", engine_version="0.1.0-foundation",
        reference_data_version="b" * 64, generated_at=datetime.now(timezone.utc),
        central_question="A hand-built, database-free question.",
        spread_name="Single Card",
        card_interpretations=(
            CardInterpretation(
                position_name="The Card", semantic_role="general", position_order=1,
                card_name="The Fool", orientation="upright",
                meaning_text="New beginnings, a leap of faith.",
                themes=("new_beginnings",), citation=citation,
            ),
        ),
        relationships=Relationships(major_arcana_count=1, minor_arcana_count=0),
        central_issue=Explained(value="new_beginnings", citations=(citation,)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(
            value="Together, the drawn cards center on new_beginnings.", citations=(citation,)
        ),
    )
    narrative = assemble_narrative(model)
    assert narrative.sections[1].statements[0].text == "New Beginnings"


def test_narrative_modules_contain_no_database_or_orm_references():
    """Static, source-level enforcement that the narrative layer never
    imports or references SQLAlchemy, sessions, or app.models -- not just
    "doesn't currently call" them, but structurally cannot by accident.
    """
    forbidden = ("sqlalchemy", "Session", "app.models", "app.db")
    for module in (assembler, sections, humanize):
        source = inspect.getsource(module)
        for token in forbidden:
            assert token not in source, f"{module.__name__} unexpectedly references {token!r}"
