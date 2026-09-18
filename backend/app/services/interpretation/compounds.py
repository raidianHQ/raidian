"""Stage 6: compound-theme matching.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stage 6 and Section 11
(Compound-Theme Architecture). Rules are represented as a Python code
registry, not database rows -- confirmed in
Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q4 (a rule's
trigger is logic, not data; the product spec's own seed set is small
enough that a rule-authoring DSL isn't justified yet).

Only two rules are seeded here. RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 11
lists seven illustrative compound names from the original product brief
("Security vs. Change", "Security vs. Departure", "Clarity vs.
Uncertainty", "Emotional Transition", "Intuition Within Uncertainty",
"Clarity Leading to Change", "Release Through Restructuring") as "a
starting seed set, not a ceiling" -- but five of the seven name concepts
("security", "departure", "change", "release", "restructuring") that do
not exist as exact tags in the canonical theme vocabulary
(theme_vocabulary.yaml) after the Reference Data Enrichment &
Normalization pass (e.g. "change" was consolidated into "transition").
Mapping those five onto today's vocabulary would mean deciding, on this
engine's own authority, which existing tag(s) the brief's words were
"really" pointing at -- exactly the kind of invented interpretive
judgment the design constraints (and RAIDIAN_WISE_THEME_VOCABULARY_V1.md's
own normalization rationale) rule out.

Only "Clarity vs. Uncertainty" and "Intuition Within Uncertainty" use tag
names that exist verbatim and unambiguously in theme_vocabulary.yaml
("clarity", "uncertainty", "intuition") -- those two are implemented.
Adding the other five is future work, gated on a deliberate decision about
how to map them (or on authoring new named compounds from scratch), not
something this foundation silently guesses at.

Both seeded rules are tier "conditional": they have an explicit, recorded
trigger condition (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 11.2), as
opposed to "core" (requires demonstrated validation across multiple
spreads/contexts, which hasn't happened) or "emergent" (an unreviewed,
ad hoc observation -- these were reviewed and deliberately authored, not
merely noticed).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.interpretive_model import Citation, RuleTier, Tension
from app.services.interpretation.citations import citation_for_draw, citation_for_rule
from app.services.interpretation.context import ReadingContext

PatternType = str  # "tension" | "theme" -- kept as plain str to avoid a second Literal alias


@dataclass(frozen=True)
class CompoundMatch:
    rule_id: str
    rule_name: str
    tier: RuleTier
    pattern_type: PatternType
    description: str
    tension: Tension | None
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class CompoundThemeRule:
    id: str
    name: str
    tier: RuleTier
    pattern_type: PatternType
    description: str
    contributing_theme_tags: tuple[str, ...]
    trigger: Callable[[ReadingContext], CompoundMatch | None]


def _draws_with_theme(reading_context: ReadingContext, theme: str) -> tuple:
    return tuple(draw for draw in reading_context.draws if theme in draw.all_themes)


def _clarity_vs_uncertainty(reading_context: ReadingContext) -> CompoundMatch | None:
    clarity_draws = _draws_with_theme(reading_context, "clarity")
    uncertainty_draws = _draws_with_theme(reading_context, "uncertainty")
    if not clarity_draws or not uncertainty_draws:
        return None

    citations = tuple(
        citation_for_draw(d, contributing_theme="clarity") for d in clarity_draws
    ) + tuple(citation_for_draw(d, contributing_theme="uncertainty") for d in uncertainty_draws)

    return CompoundMatch(
        rule_id="clarity_vs_uncertainty",
        rule_name="Clarity vs. Uncertainty",
        tier="conditional",
        pattern_type="tension",
        description=(
            "Cards contributing 'clarity' and cards contributing 'uncertainty' both appear "
            "in this spread."
        ),
        tension=Tension(pole_a="clarity", pole_b="uncertainty", label="Clarity vs. Uncertainty"),
        citations=citations,
    )


def _intuition_within_uncertainty(reading_context: ReadingContext) -> CompoundMatch | None:
    intuition_draws = _draws_with_theme(reading_context, "intuition")
    uncertainty_draws = _draws_with_theme(reading_context, "uncertainty")
    if not intuition_draws or not uncertainty_draws:
        return None

    citations = tuple(
        citation_for_draw(d, contributing_theme="intuition") for d in intuition_draws
    ) + tuple(citation_for_draw(d, contributing_theme="uncertainty") for d in uncertainty_draws)

    return CompoundMatch(
        rule_id="intuition_within_uncertainty",
        rule_name="Intuition Within Uncertainty",
        tier="conditional",
        pattern_type="theme",
        description=(
            "Cards contributing 'intuition' appear alongside cards contributing 'uncertainty' "
            "in this spread."
        ),
        tension=None,
        citations=citations,
    )


# Registry order is the tiebreak for which match becomes primary_tension
# when more than one tension-type rule fires (engine.py). Order is a fixed
# tuple literal, not derived from a dict/set, so it is itself deterministic.
RULE_REGISTRY: tuple[CompoundThemeRule, ...] = (
    CompoundThemeRule(
        id="clarity_vs_uncertainty",
        name="Clarity vs. Uncertainty",
        tier="conditional",
        pattern_type="tension",
        description="Named compound from RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 11's seed set.",
        contributing_theme_tags=("clarity", "uncertainty"),
        trigger=_clarity_vs_uncertainty,
    ),
    CompoundThemeRule(
        id="intuition_within_uncertainty",
        name="Intuition Within Uncertainty",
        tier="conditional",
        pattern_type="theme",
        description="Named compound from RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 11's seed set.",
        contributing_theme_tags=("intuition", "uncertainty"),
        trigger=_intuition_within_uncertainty,
    ),
)


def match_compounds(reading_context: ReadingContext) -> tuple[CompoundMatch, ...]:
    """Evaluates every rule in RULE_REGISTRY, in registry order. Order of
    the returned tuple is always registry order (a fixed literal), never
    dependent on set/dict iteration.
    """
    matches = []
    for rule in RULE_REGISTRY:
        match = rule.trigger(reading_context)
        if match is not None:
            matches.append(match)
    return tuple(matches)


def citation_for_matched_rule(match: CompoundMatch) -> Citation:
    return citation_for_rule(rule_id=match.rule_id, rule_tier=match.tier)
