"""The deterministic Interpretation Engine's pipeline orchestrator.

Wires together every stage module in
RAIDIAN_WISE_ARCHITECTURE_V1.md Section 6 / Section 2's proposed layout
into the pipeline shape from RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9.1,
and assembles their outputs into one InterpretiveModel.

Pure function: `interpret()` performs one read-only reference-data query
(for reference_data_version) and otherwise touches no database and has no
side effects -- it returns an InterpretiveModel, it does not persist one.
Persistence is a separate, deliberately thin concern (persistence.py),
mirroring the loader/seed split this project already uses elsewhere
(Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 8).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.reading import Reading
from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Explained,
    InterpretiveModel,
    Relationships,
    SuitClusterSummary,
    Tension,
    ThemeStrength,
    Trajectory,
)
from app.services.interpretation.citations import citation_for_draw
from app.services.interpretation.compounds import CompoundMatch, citation_for_matched_rule, match_compounds
from app.services.interpretation.context import DrawContext, ReadingContext, build_reading_context
from app.services.interpretation.contradictions import detect_contradictions
from app.services.interpretation.evidence import identify_uncertainty, score_evidence_strength
from app.services.interpretation.meanings import ThemeScore, resolve_meanings, score_theme_strength
from app.services.interpretation.reference_data_version import compute_reference_data_version
from app.services.interpretation.relationships import CardRelationships, SuitCluster, evaluate_relationships
from app.services.interpretation.relevance import apply_position_relevance, apply_question_relevance
from app.services.interpretation.structure import StructuralFindings, evaluate_structure
from app.services.interpretation.trajectory import derive_trajectory

SCHEMA_VERSION = "1.0"

# Bumped whenever pipeline *logic* changes (a new stage, a changed scoring
# rule, a new/changed compound-theme rule) -- see
# Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q2's
# cross-reference: engine_version covers code changes, reference_data_version
# covers reference-data content changes. This is intentionally distinct
# from SCHEMA_VERSION, which only changes if InterpretiveModel's own shape
# changes.
ENGINE_VERSION = "0.1.0-foundation"

_SUPPORTING_THEMES_LIMIT = 3


def _derive_central_issue(theme_scores: tuple[ThemeScore, ...]) -> Explained[str]:
    # theme_scores is already sorted (count desc, theme name asc) by
    # meanings.score_theme_strength -- the first entry is the single most
    # broadly-supported theme across the drawn cards. A richer synthesis
    # (combining multiple top themes into a phrase) is deferred to a future
    # engine iteration rather than invented here as unfounded prose.
    top = theme_scores[0]
    return Explained(value=top.theme, citations=top.citations)


def _derive_primary_tension(
    compound_matches: tuple[CompoundMatch, ...],
) -> tuple[Explained[Tension] | None, tuple[CompoundMatch, ...]]:
    """Returns (primary_tension, remaining_matches). The first
    pattern_type == "tension" match in registry order becomes
    primary_tension; every other match (tension or theme type) is left in
    `remaining_matches` for supporting_themes to pick up.
    """
    for match in compound_matches:
        if match.pattern_type == "tension" and match.tension is not None:
            citations = match.citations + (citation_for_matched_rule(match),)
            explained = Explained(value=match.tension, citations=citations)
            remaining = tuple(m for m in compound_matches if m is not match)
            return explained, remaining
    return None, compound_matches


def _derive_supporting_themes(
    theme_scores: tuple[ThemeScore, ...],
    central_issue_theme: str,
    remaining_compound_matches: tuple[CompoundMatch, ...],
) -> tuple[Explained[str], ...]:
    supporting: list[Explained[str]] = []

    for score in theme_scores:
        if score.theme == central_issue_theme:
            continue
        if len(supporting) >= _SUPPORTING_THEMES_LIMIT:
            break
        supporting.append(Explained(value=score.theme, citations=score.citations))

    for match in remaining_compound_matches:
        citations = match.citations + (citation_for_matched_rule(match),)
        supporting.append(Explained(value=match.rule_name, citations=citations))

    return tuple(supporting)


def _derive_role_explained(
    draw: DrawContext, *, extra_citations: tuple[Citation, ...] = ()
) -> Explained[str]:
    theme = draw.primary_themes[0] if draw.primary_themes else draw.card_name
    own_citation = citation_for_draw(draw, contributing_theme=theme if draw.primary_themes else None)
    return Explained(value=theme, citations=(own_citation, *extra_citations))


def _derive_blocker(structure: StructuralFindings) -> Explained[str] | None:
    if structure.blocker is None:
        return None
    return _derive_role_explained(structure.blocker)


def _derive_advice(structure: StructuralFindings) -> Explained[str] | None:
    if structure.advice is None:
        return None
    return _derive_role_explained(structure.advice)


def _derive_clarification(structure: StructuralFindings) -> Explained[str] | None:
    if structure.advice is None or structure.advice_clarifier is None:
        return None
    return _derive_role_explained(
        structure.advice_clarifier,
        extra_citations=(citation_for_draw(structure.advice),),
    )


def _to_card_interpretation(draw: DrawContext, meanings: dict[UUID, str]) -> CardInterpretation:
    return CardInterpretation(
        position_name=draw.position_name,
        semantic_role=draw.semantic_role.value,
        position_order=draw.position_order,
        card_name=draw.card_name,
        orientation=draw.orientation.value,
        meaning_text=meanings[draw.card_draw_id],
        themes=draw.all_themes,
        citation=citation_for_draw(draw),
    )


def _to_suit_cluster_summary(cluster: SuitCluster) -> SuitClusterSummary:
    return SuitClusterSummary(
        suit=cluster.suit.value,
        card_names=tuple(d.card_name for d in cluster.draws),
        citations=tuple(citation_for_draw(d) for d in cluster.draws),
    )


def _derive_relationships(
    reading_context: ReadingContext, relationships: CardRelationships
) -> Relationships:
    return Relationships(
        same_suit_clusters=tuple(_to_suit_cluster_summary(c) for c in relationships.same_suit_clusters),
        major_arcana_count=relationships.major_arcana_count,
        minor_arcana_count=len(reading_context.draws) - relationships.major_arcana_count,
    )


_SYNTHESIS_REINFORCED_THEMES_LIMIT = 2
"""Keeps the synthesis sentence concise (task requirement) -- a hard cap,
not a ranking judgment beyond theme_scores' own existing, already-approved
count-desc/name-asc order (meanings.py Rule T1).
"""


def _derive_deterministic_synthesis(
    *,
    central_issue: Explained[str],
    theme_scores: tuple[ThemeScore, ...],
    primary_tension: Explained[Tension] | None,
    relationships: Relationships,
    trajectory: Explained[Trajectory] | None,
    blocker: Explained[str] | None,
    advice: Explained[str] | None,
) -> Explained[str]:
    """Assembles one concise, citation-backed statement of what the drawn
    cards establish TOGETHER -- combining conclusions the pipeline's own
    earlier stages already reached, never a new tarot-symbolic claim of
    its own (the same "no net-new claims" discipline
    NARRATIVE_LAYER_DESIGN.md Section 6, Rule N10 already established for
    its own "Overall Reflection" recap -- see that rule's own rationale:
    "any attempt at genuine synthesis... would necessarily either
    duplicate engine logic... or invent something the engine never
    concluded"). This lives at the engine layer specifically so it can
    carry real citations (N10 deliberately carries none) and so any
    consumer of InterpretiveModel has a synthesis available without
    running Narrative assembly at all.

    Values are left in their raw, closed-vocabulary form (snake_case
    theme tags, etc.) -- exactly like central_issue/blocker/advice
    already are -- never humanized here; humanize_tag() is a Narrative-
    layer-only concern (humanize.py's own docstring) the engine must not
    import, so a later narrative/AI layer is still expected to render
    this text for an end user, not consume it verbatim.
    """
    clauses = [f"the drawn cards center on {central_issue.value}"]
    citations: list[Citation] = list(central_issue.citations)

    reinforced = tuple(
        score for score in theme_scores if score.theme != central_issue.value and score.count >= 2
    )[:_SYNTHESIS_REINFORCED_THEMES_LIMIT]
    if reinforced:
        names = ", ".join(score.theme for score in reinforced)
        clauses.append(f"reinforced by more than one card in the themes of {names}")
        for score in reinforced:
            citations.extend(score.citations)

    if primary_tension is not None:
        clauses.append(f"held in tension as {primary_tension.value.label}")
        citations.extend(primary_tension.citations)

    if relationships.same_suit_clusters:
        cluster = relationships.same_suit_clusters[0]
        clauses.append(f"including {len(cluster.card_names)} cards sharing the suit of {cluster.suit}")
        citations.extend(cluster.citations)

    if trajectory is not None:
        first_step = trajectory.value.arc[0]
        last_step = trajectory.value.arc[-1]
        clauses.append(f"tracing a path from {first_step.card_name} toward {last_step.card_name}")
        citations.extend(trajectory.citations)

    if blocker is not None:
        clauses.append(f"naming {blocker.value} as a structural blocker")
        citations.extend(blocker.citations)

    if advice is not None:
        clauses.append(f"pointing toward {advice.value} as the spread's own structural guidance")
        citations.extend(advice.citations)

    text = "Together, " + "; ".join(clauses) + "."
    deduped_citations = tuple(dict.fromkeys(citations))
    return Explained(value=text, citations=deduped_citations)


def interpret(reading: Reading, session: Session) -> InterpretiveModel:
    """Runs the full deterministic pipeline against `reading` and returns
    the resulting InterpretiveModel. Does not persist anything -- see
    persistence.save_interpretation for that.

    `reading` must have at least one CardDraw (a spread-complete Reading);
    interpreting an empty/in-progress Reading is a caller error, not
    something this function silently tolerates.
    """
    reading_context: ReadingContext = build_reading_context(reading)
    if not reading_context.draws:
        raise ValueError(
            f"cannot interpret reading {reading.id}: it has no card draws "
            "(the reading must be spread-complete before interpretation)"
        )

    # Stage 1-2
    meanings = resolve_meanings(reading_context)  # keyed by card_draw_id, quoted in card_interpretations below
    theme_scores = score_theme_strength(reading_context)

    # Stage 3-4 (explicit no-ops -- see relevance.py)
    theme_scores = apply_question_relevance(theme_scores, reading_context)
    theme_scores = apply_position_relevance(theme_scores, reading_context)

    # Stage 5 -- exposed via the `relationships` output field below
    # (Documentation/INTERPRETATION_RULES_DESIGN.md Section 7.1); never
    # fed into supporting_themes or evidence_strength (Rules R3/R4's
    # still-honored restriction -- see Relationships' own docstring).
    card_relationships = evaluate_relationships(reading_context)

    # Stage 6
    compound_matches = match_compounds(reading_context)

    # Stage 7
    structure = evaluate_structure(reading_context)

    # Stage 8
    trajectory = derive_trajectory(reading_context)

    # Stage 9
    contradictions = detect_contradictions(reading_context, compound_matches)

    # Assemble final-field values from the stage outputs above
    primary_tension, remaining_matches = _derive_primary_tension(compound_matches)
    central_issue = _derive_central_issue(theme_scores)
    supporting_themes = _derive_supporting_themes(theme_scores, central_issue.value, remaining_matches)
    blocker = _derive_blocker(structure)
    advice = _derive_advice(structure)
    clarification = _derive_clarification(structure)

    # Stage 10-11
    uncertainty = identify_uncertainty(structure, trajectory, compound_matches)
    evidence_strength = score_evidence_strength(structure, trajectory, compound_matches)

    reference_data_version = compute_reference_data_version(session)

    # Structured synthesis: individual card interpretations, relationships,
    # full theme-strength ranking, and the deterministic "together" synthesis.
    card_interpretations = tuple(
        _to_card_interpretation(draw, meanings) for draw in reading_context.draws
    )
    relationships = _derive_relationships(reading_context, card_relationships)
    theme_strength = tuple(
        ThemeStrength(theme=score.theme, count=score.count, citations=score.citations)
        for score in theme_scores
    )
    deterministic_synthesis = _derive_deterministic_synthesis(
        central_issue=central_issue,
        theme_scores=theme_scores,
        primary_tension=primary_tension,
        relationships=relationships,
        trajectory=trajectory,
        blocker=blocker,
        advice=advice,
    )

    return InterpretiveModel(
        schema_version=SCHEMA_VERSION,
        engine_version=ENGINE_VERSION,
        reference_data_version=reference_data_version,
        generated_at=datetime.now(timezone.utc),
        central_question=reading_context.question,
        spread_name=reading_context.spread_name,
        spread_description=reading_context.spread_description,
        card_interpretations=card_interpretations,
        relationships=relationships,
        theme_strength=theme_strength,
        central_issue=central_issue,
        primary_tension=primary_tension,
        supporting_themes=supporting_themes,
        trajectory=trajectory,
        blocker=blocker,
        uncertainty=uncertainty,
        advice=advice,
        clarification=clarification,
        contradictions=contradictions,
        evidence_strength=evidence_strength,
        deterministic_synthesis=deterministic_synthesis,
    )
