"""Stage 3-4: question relevance + position relevance.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stages 3-4.

Both stages are explicit, documented pass-throughs for this foundation
phase -- see Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q3.
The functions exist (so the pipeline's stage structure is complete and
future weighting logic has a designated home) but perform no reweighting
yet. This is a deliberate decision, not a placeholder left unfinished by
accident.
"""

from __future__ import annotations

from app.services.interpretation.context import ReadingContext
from app.services.interpretation.meanings import ThemeScore


def apply_question_relevance(
    theme_scores: tuple[ThemeScore, ...], reading_context: ReadingContext
) -> tuple[ThemeScore, ...]:
    """Stage 3: intentionally a no-op.

    `question_domain` has no fixed taxonomy (product spec's own Section 16
    Q6 was never resolved), so this stage must not weight themes by it --
    doing so would mean inventing an unreviewed heuristic. `question_domain`
    is still accepted here (not ignored/dropped from the signature) so a
    future, real implementation can add weighting without changing this
    stage's position in the pipeline or its call signature.
    """
    del reading_context  # accepted for signature stability; unused by design (Q3)
    return theme_scores


def apply_position_relevance(
    theme_scores: tuple[ThemeScore, ...], reading_context: ReadingContext
) -> tuple[ThemeScore, ...]:
    """Stage 4: intentionally a no-op for this foundation phase.

    Structural/positional context is already carried on every citation
    (Citation.position_name / position_semantic_role, set in
    meanings.score_theme_strength via citations.citation_for_draw) -- so
    "which position a theme came from" is never lost. What this stage does
    NOT yet do is apply a numeric reweighting (e.g. boosting themes drawn
    from a `situation` or `significator` position over a `general` one),
    because no such weighting formula is specified anywhere in the product
    spec or design doc, and inventing one would be inventing interpretation
    logic rather than implementing it.
    """
    del reading_context  # accepted for signature stability; unused by design
    return theme_scores
