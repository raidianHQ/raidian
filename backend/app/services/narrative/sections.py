"""N1-N10 section-assembly rules.

Each function implements exactly one rule from
Documentation/NARRATIVE_LAYER_DESIGN.md Section 6, reading only its
documented InterpretiveModel source field(s), forwarding citations
verbatim, and never constructing a new Citation or re-deriving a
conclusion the engine already made (design doc Section 2 -- "no new
facts", "no re-derivation").

Every function takes the full InterpretiveModel (never a database
session, never any other input) and returns exactly one NarrativeSection.
"""

from __future__ import annotations

from app.schemas.interpretive_model import Explained, InterpretiveModel
from app.schemas.narrative_model import NarrativeSection, NarrativeStatement
from app.services.narrative.humanize import humanize_tag

# Fixed disclaimer required by RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section
# 10.11: evidence_strength must never be shown without this distinction
# stated alongside it. Part of the template, not derived from data --
# carries no citation.
_EVIDENCE_STRENGTH_DISCLAIMER = (
    "This reflects how well the drawn cards and their relationships support "
    "the reading's conclusions -- it is not a prediction of what will happen."
)

# Fixed fallback for Rule N7 when `uncertainty` is present but empty (a
# real, validated case -- INTERPRETATION_ENGINE_VALIDATION.md Section 8.2).
# States only that the checklist found nothing to name, never that the
# reading is complete or fully resolved. Carries no citation -- it is not
# derived from any specific evidence, only from the list's own emptiness.
_NO_UNCERTAINTY_STATEMENTS_FALLBACK = (
    "This reading's current structural and thematic checks did not identify "
    "any additional gaps to name."
)


def _themed_statement(explained: Explained[str]) -> NarrativeStatement:
    return NarrativeStatement(text=humanize_tag(explained.value), citations=explained.citations)


def assemble_your_reading(model: InterpretiveModel) -> NarrativeSection:
    """Rule N1 -- "Your Reading". Always present. Synthesizes
    central_question (verbatim, uncited) and evidence_strength (humanized,
    always paired with its mandatory disclaimer, uncited).
    """
    question_statement = NarrativeStatement(text=model.central_question, citations=())
    evidence_statement = NarrativeStatement(
        text=f"Evidence strength: {humanize_tag(model.evidence_strength)}. "
        f"{_EVIDENCE_STRENGTH_DISCLAIMER}",
        citations=(),
    )
    return NarrativeSection(
        id="your_reading",
        title="Your Reading",
        source_field=None,
        present=True,
        statements=(question_statement, evidence_statement),
    )


def assemble_central_theme(model: InterpretiveModel) -> NarrativeSection:
    """Rule N2 -- "Central Theme". Always present (central_issue is never
    null -- INTERPRETATION_ENGINE_DESIGN.md Section 4.1's contract).
    """
    return NarrativeSection(
        id="central_theme",
        title="Central Theme",
        source_field="central_issue",
        present=True,
        statements=(_themed_statement(model.central_issue),),
    )


def assemble_the_tension(model: InterpretiveModel) -> NarrativeSection:
    """Rule N3 -- "The Tension". Present only when primary_tension is not
    None. Tension.label is already human-readable and is used as-is;
    pole_a/pole_b are raw theme tags and are humanized.
    """
    tension = model.primary_tension
    if tension is None:
        return NarrativeSection(
            id="the_tension",
            title="The Tension",
            source_field="primary_tension",
            present=False,
        )
    pole_a = humanize_tag(tension.value.pole_a)
    pole_b = humanize_tag(tension.value.pole_b)
    text = f"{tension.value.label}: a tension between {pole_a} and {pole_b}."
    return NarrativeSection(
        id="the_tension",
        title="The Tension",
        source_field="primary_tension",
        present=True,
        statements=(NarrativeStatement(text=text, citations=tension.citations),),
    )


def assemble_what_stands_in_the_way(model: InterpretiveModel) -> NarrativeSection:
    """Rule N4 -- "What Stands in the Way". Present only when blocker is
    not None. Deliberately its own section, independent of primary_tension
    -- see design doc Section 6, Rule N4's note on why the two must not be
    conflated.
    """
    blocker = model.blocker
    if blocker is None:
        return NarrativeSection(
            id="what_stands_in_the_way",
            title="What Stands in the Way",
            source_field="blocker",
            present=False,
        )
    return NarrativeSection(
        id="what_stands_in_the_way",
        title="What Stands in the Way",
        source_field="blocker",
        present=True,
        statements=(_themed_statement(blocker),),
    )


def assemble_what_the_spread_shows(model: InterpretiveModel) -> NarrativeSection:
    """Rule N5 -- "What the Spread Shows". Present whenever
    supporting_themes or contradictions is non-empty. Each entry keeps its
    own citations -- never merged into one section-level list (design doc
    Section 6, Rule N5).
    """
    theme_statements = tuple(_themed_statement(entry) for entry in model.supporting_themes)
    contradiction_statements = tuple(
        NarrativeStatement(text=contradiction.description, citations=contradiction.sources)
        for contradiction in model.contradictions
    )
    statements = theme_statements + contradiction_statements
    return NarrativeSection(
        id="what_the_spread_shows",
        title="What the Spread Shows",
        source_field="supporting_themes+contradictions",
        present=bool(statements),
        statements=statements,
    )


def assemble_where_things_appear_to_be_moving(model: InterpretiveModel) -> NarrativeSection:
    """Rule N6 -- "Where Things Appear to Be Moving". Present only when
    trajectory is not None. trajectory.value.arc and trajectory.citations
    are built in lockstep by trajectory.py (one citation per step, same
    order), so zipping them pairs each step with exactly its own citation
    -- never trajectory.citations as one undifferentiated list.
    """
    trajectory = model.trajectory
    if trajectory is None:
        return NarrativeSection(
            id="where_things_appear_to_be_moving",
            title="Where Things Appear to Be Moving",
            source_field="trajectory",
            present=False,
        )
    statements = tuple(
        NarrativeStatement(
            text=f"{humanize_tag(step.semantic_role)}: {step.card_name} "
            f"({humanize_tag(step.orientation)}).",
            citations=(citation,),
        )
        for step, citation in zip(trajectory.value.arc, trajectory.citations, strict=True)
    )
    return NarrativeSection(
        id="where_things_appear_to_be_moving",
        title="Where Things Appear to Be Moving",
        source_field="trajectory",
        present=True,
        statements=statements,
    )


def assemble_what_may_be_unclear(model: InterpretiveModel) -> NarrativeSection:
    """Rule N7 -- "What May Be Unclear". Structurally always present
    (uncertainty is a required InterpretiveModel field). When the list is
    empty, renders the fixed, uncited fallback rather than silence or an
    invented claim (design doc Section 10, Rule N10b)."""
    if model.uncertainty:
        statements = tuple(
            NarrativeStatement(text=text, citations=()) for text in model.uncertainty
        )
    else:
        statements = (NarrativeStatement(text=_NO_UNCERTAINTY_STATEMENTS_FALLBACK, citations=()),)
    return NarrativeSection(
        id="what_may_be_unclear",
        title="What May Be Unclear",
        source_field="uncertainty",
        present=True,
        statements=statements,
    )


def assemble_advice(model: InterpretiveModel) -> NarrativeSection:
    """Rule N9 (advice half) -- "Advice". Present only when advice is not
    None."""
    advice = model.advice
    if advice is None:
        return NarrativeSection(
            id="advice", title="Advice", source_field="advice", present=False
        )
    return NarrativeSection(
        id="advice",
        title="Advice",
        source_field="advice",
        present=True,
        statements=(_themed_statement(advice),),
    )


def assemble_clarification(model: InterpretiveModel) -> NarrativeSection:
    """Rule N9 (clarification half) -- "Clarification". Present only when
    clarification is not None -- which, per
    INTERPRETATION_RULES_DESIGN.md Rule A6, can only be non-null when
    advice is also non-null, so this section never appears without
    "Advice" by construction of the upstream engine, not by any check
    added here.
    """
    clarification = model.clarification
    if clarification is None:
        return NarrativeSection(
            id="clarification", title="Clarification", source_field="clarification", present=False
        )
    return NarrativeSection(
        id="clarification",
        title="Clarification",
        source_field="clarification",
        present=True,
        statements=(_themed_statement(clarification),),
    )


def assemble_overall_reflection(model: InterpretiveModel) -> NarrativeSection:
    """Rule N10 -- "Overall Reflection". Always present. A fixed-algorithm
    recap ONLY: every clause re-references a value already rendered by an
    earlier section (central theme, tension label, trajectory's final
    step, advice) via fixed connective phrases -- nothing is computed
    fresh, and the section carries no citations of its own (design doc
    Section 6, Rule N10: consumers needing citations for a recap clause
    should look at the earlier section it restates).
    """
    clauses = [f"this reading centers on {humanize_tag(model.central_issue.value)}"]

    if model.primary_tension is not None:
        clauses.append(f"held in tension as {model.primary_tension.value.label}")

    if model.trajectory is not None:
        final_step = model.trajectory.value.arc[-1]
        clauses.append(
            f"moving toward {final_step.card_name} in the "
            f"{humanize_tag(final_step.semantic_role)} position"
        )

    if model.advice is not None:
        clauses.append(f"with guidance centered on {humanize_tag(model.advice.value)}")

    text = "In summary, " + "; ".join(clauses) + "."
    return NarrativeSection(
        id="overall_reflection",
        title="Overall Reflection",
        source_field=None,
        present=True,
        statements=(NarrativeStatement(text=text, citations=()),),
    )
