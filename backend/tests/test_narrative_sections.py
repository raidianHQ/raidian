"""Unit tests for each N1-N10 section-assembly rule
(NARRATIVE_LAYER_DESIGN.md Section 6), against hand-constructed
InterpretiveModel fixtures. No database, no seeded_session -- proves the
rules themselves need nothing beyond an InterpretiveModel instance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.interpretive_model import (
    Citation,
    Contradiction,
    Explained,
    InterpretiveModel,
    Trajectory,
    TrajectoryStep,
    Tension,
)
from app.services.narrative.sections import (
    assemble_advice,
    assemble_central_theme,
    assemble_clarification,
    assemble_overall_reflection,
    assemble_the_tension,
    assemble_what_may_be_unclear,
    assemble_what_stands_in_the_way,
    assemble_what_the_spread_shows,
    assemble_where_things_appear_to_be_moving,
    assemble_your_reading,
)


def _citation(theme: str = "clarity", card_name: str = "Ace of Swords") -> Citation:
    return Citation(
        source_type="card_draw",
        card_draw_id=uuid4(),
        card_name=card_name,
        position_name="Situation",
        position_semantic_role="situation",
        contributing_theme=theme,
    )


def _base_model(**overrides) -> InterpretiveModel:
    defaults: dict = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on right now?",
        central_issue=Explained(value="clarity", citations=(_citation("clarity"),)),
        primary_tension=None,
        supporting_themes=(),
        trajectory=None,
        blocker=None,
        uncertainty=(),
        advice=None,
        clarification=None,
        contradictions=(),
        evidence_strength="unresolved",
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


# --- N1: Your Reading -------------------------------------------------------


def test_your_reading_is_always_present_and_quotes_question_verbatim():
    model = _base_model(central_question="Will this collaboration go well?")
    section = assemble_your_reading(model)
    assert section.present is True
    assert section.statements[0].text == "Will this collaboration go well?"
    assert section.statements[0].citations == ()


def test_your_reading_states_evidence_strength_with_mandatory_disclaimer():
    model = _base_model(evidence_strength="strong")
    section = assemble_your_reading(model)
    evidence_text = section.statements[1].text
    assert "Strong" in evidence_text
    assert "not a prediction" in evidence_text


# --- N2: Central Theme -------------------------------------------------------


def test_central_theme_is_always_present_and_humanized():
    citation = _citation("new_beginnings")
    model = _base_model(central_issue=Explained(value="new_beginnings", citations=(citation,)))
    section = assemble_central_theme(model)
    assert section.present is True
    assert section.statements[0].text == "New Beginnings"
    assert section.statements[0].citations == (citation,)


# --- N3: The Tension ---------------------------------------------------------


def test_the_tension_is_absent_when_primary_tension_is_none():
    model = _base_model(primary_tension=None)
    section = assemble_the_tension(model)
    assert section.present is False
    assert section.statements == ()


def test_the_tension_renders_label_and_humanized_poles_when_present():
    citation = _citation("clarity")
    tension = Explained(
        value=Tension(pole_a="clarity", pole_b="uncertainty", label="Clarity vs. Uncertainty"),
        citations=(citation,),
    )
    model = _base_model(primary_tension=tension)
    section = assemble_the_tension(model)
    assert section.present is True
    text = section.statements[0].text
    assert "Clarity vs. Uncertainty" in text
    assert "Clarity" in text and "Uncertainty" in text
    assert section.statements[0].citations == (citation,)


# --- N4: What Stands in the Way ----------------------------------------------


def test_what_stands_in_the_way_is_absent_when_blocker_is_none():
    section = assemble_what_stands_in_the_way(_base_model(blocker=None))
    assert section.present is False


def test_what_stands_in_the_way_present_independent_of_primary_tension():
    """Blocker and primary_tension are independent fields -- a blocker can
    be present while primary_tension is null (design doc Rule N4's note).
    """
    citation = _citation("indecision")
    model = _base_model(
        blocker=Explained(value="indecision", citations=(citation,)),
        primary_tension=None,
    )
    section = assemble_what_stands_in_the_way(model)
    assert section.present is True
    assert section.statements[0].text == "Indecision"
    assert section.statements[0].citations == (citation,)


# --- N5: What the Spread Shows -----------------------------------------------


def test_what_the_spread_shows_absent_when_both_sources_empty():
    section = assemble_what_the_spread_shows(_base_model(supporting_themes=(), contradictions=()))
    assert section.present is False
    assert section.statements == ()


def test_what_the_spread_shows_one_statement_per_supporting_theme_with_own_citations():
    c1, c2 = _citation("hope"), _citation("renewal")
    model = _base_model(
        supporting_themes=(
            Explained(value="hope", citations=(c1,)),
            Explained(value="renewal", citations=(c2,)),
        )
    )
    section = assemble_what_the_spread_shows(model)
    assert section.present is True
    assert [s.text for s in section.statements] == ["Hope", "Renewal"]
    assert section.statements[0].citations == (c1,)
    assert section.statements[1].citations == (c2,)


def test_what_the_spread_shows_includes_contradictions_with_their_own_sources():
    theme_citation = _citation("hope")
    contradiction_sources = (_citation("hope"), _citation("grief"))
    model = _base_model(
        supporting_themes=(Explained(value="hope", citations=(theme_citation,)),),
        contradictions=(
            Contradiction(description="Hope and grief both appear.", sources=contradiction_sources),
        ),
    )
    section = assemble_what_the_spread_shows(model)
    assert section.statements[-1].text == "Hope and grief both appear."
    assert section.statements[-1].citations == contradiction_sources


# --- N6: Where Things Appear to Be Moving ------------------------------------


def test_trajectory_section_absent_when_trajectory_is_none():
    section = assemble_where_things_appear_to_be_moving(_base_model(trajectory=None))
    assert section.present is False


def test_trajectory_section_one_statement_per_step_with_matching_citation():
    c1, c2 = _citation(card_name="The Fool"), _citation(card_name="Ace of Swords")
    trajectory = Explained(
        value=Trajectory(
            arc=(
                TrajectoryStep(
                    position_name="Recent Past", semantic_role="recent_past",
                    card_name="The Fool", orientation="upright",
                ),
                TrajectoryStep(
                    position_name="Situation", semantic_role="situation",
                    card_name="Ace of Swords", orientation="reversed",
                ),
            )
        ),
        citations=(c1, c2),
    )
    model = _base_model(trajectory=trajectory)
    section = assemble_where_things_appear_to_be_moving(model)
    assert section.present is True
    assert len(section.statements) == 2
    assert "Recent Past" in section.statements[0].text
    assert "The Fool" in section.statements[0].text
    assert "Upright" in section.statements[0].text
    assert section.statements[0].citations == (c1,)
    assert "Situation" in section.statements[1].text
    assert "Reversed" in section.statements[1].text
    assert section.statements[1].citations == (c2,)


# --- N7: What May Be Unclear --------------------------------------------------


def test_uncertainty_section_always_present_even_when_empty():
    section = assemble_what_may_be_unclear(_base_model(uncertainty=()))
    assert section.present is True
    assert len(section.statements) == 1
    assert "did not identify" in section.statements[0].text
    assert section.statements[0].citations == ()


def test_uncertainty_section_lists_each_statement_verbatim_uncited():
    statements = ("No Advice position exists.", "No Blocker position exists.")
    section = assemble_what_may_be_unclear(_base_model(uncertainty=statements))
    assert [s.text for s in section.statements] == list(statements)
    assert all(s.citations == () for s in section.statements)


# --- N8/N9: Advice + Clarification -------------------------------------------


def test_advice_absent_when_none():
    assert assemble_advice(_base_model(advice=None)).present is False


def test_advice_present_and_humanized():
    citation = _citation("introspection")
    model = _base_model(advice=Explained(value="introspection", citations=(citation,)))
    section = assemble_advice(model)
    assert section.present is True
    assert section.statements[0].text == "Introspection"
    assert section.statements[0].citations == (citation,)


def test_clarification_absent_when_none():
    assert assemble_clarification(_base_model(clarification=None)).present is False


def test_clarification_present_and_humanized():
    citation = _citation("clarity")
    model = _base_model(clarification=Explained(value="clarity", citations=(citation,)))
    section = assemble_clarification(model)
    assert section.present is True
    assert section.statements[0].text == "Clarity"


# --- N10: Overall Reflection --------------------------------------------------


def test_overall_reflection_always_present_and_uncited():
    section = assemble_overall_reflection(_base_model())
    assert section.present is True
    assert section.statements[0].citations == ()


def test_overall_reflection_recaps_only_already_rendered_values():
    tension = Explained(
        value=Tension(pole_a="clarity", pole_b="uncertainty", label="Clarity vs. Uncertainty"),
        citations=(_citation(),),
    )
    trajectory = Explained(
        value=Trajectory(
            arc=(
                TrajectoryStep(
                    position_name="Near Future", semantic_role="near_future",
                    card_name="The Moon", orientation="upright",
                ),
            )
        ),
        citations=(_citation(card_name="The Moon"),),
    )
    advice = Explained(value="patience", citations=(_citation("patience"),))
    model = _base_model(
        central_issue=Explained(value="clarity", citations=(_citation(),)),
        primary_tension=tension,
        trajectory=trajectory,
        advice=advice,
    )
    section = assemble_overall_reflection(model)
    text = section.statements[0].text
    assert "Clarity" in text or "clarity" in text
    assert "Clarity vs. Uncertainty" in text
    assert "The Moon" in text
    assert "Patience" in text or "patience" in text
