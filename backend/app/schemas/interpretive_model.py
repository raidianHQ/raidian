"""The structured, machine-readable output contract of the deterministic
Interpretation Engine.

This concretizes RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 10 (The
Interpretive Model) into a typed schema, per
Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 4. Every field's
provenance requirement is documented there -- this module is deliberately
just data shape, no computation.

Field-level citations (not a separate global map) were a documented
refinement over the original architecture sketch -- see design doc Section
4.2 for why.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

EvidenceStrength = Literal["strong", "moderate", "weak", "unresolved"]
SourceType = Literal["card_draw", "compound_rule", "structural_rule"]
RuleTier = Literal["core", "conditional", "emergent"]
OrientationLiteral = Literal["upright", "reversed"]
SuitLiteral = Literal["wands", "cups", "swords", "pentacles"]


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Citation(_Model):
    """Points to exactly one piece of evidence that supported a conclusion.

    Either a card_draw citation (source_type == "card_draw", with
    card_draw_id and the denormalized display fields populated) or a rule
    citation (source_type in {"compound_rule", "structural_rule"}, with
    rule_id/rule_tier populated). Never both kinds of field populated at
    once -- see validate_reference_data_version-style validators in
    services/interpretation if stricter enforcement is later needed;
    foundation-stage callers are trusted to construct these correctly.
    """

    source_type: SourceType
    card_draw_id: UUID | None = None
    card_name: str | None = None
    position_name: str | None = None
    position_semantic_role: str | None = None
    contributing_theme: str | None = None
    rule_id: str | None = None
    rule_tier: RuleTier | None = None


class Explained(_Model, Generic[T]):
    """A conclusion plus the evidence that supports it.

    citations must never be empty -- an unsupported conclusion is a
    construction bug, not a valid output (design doc Section 4.1).
    """

    value: T
    citations: tuple[Citation, ...] = Field(min_length=1)


class Tension(_Model):
    pole_a: str
    pole_b: str
    label: str


class TrajectoryStep(_Model):
    position_name: str
    semantic_role: str
    card_name: str
    orientation: OrientationLiteral


class Trajectory(_Model):
    arc: tuple[TrajectoryStep, ...]


class Contradiction(_Model):
    description: str
    sources: tuple[Citation, ...] = Field(min_length=2)


class CardInterpretation(_Model):
    """One drawn card's individual interpretation, in its position --
    Product Spec synthesis items 1 (individual card interpretations) and
    2 (position meaning/context) combined into one entry per draw, since
    every currently-interpretable Reading's positions and drawn cards are
    already in 1:1 correspondence (there is no seeded Spread with an
    undrawn optional position -- see
    Documentation/READING_DETAIL_API_DESIGN.md's own finding of the same
    gap). Ordered by position_order, matching ReadingContext.draws.

    `meaning_text` is the same base_meaning_upright/reversed text
    resolve_meanings() (meanings.py, Rule M1) already resolves -- quoted
    verbatim, never rephrased. `themes` is the draw's own
    DrawContext.all_themes (primary then secondary, deduped) -- the same
    tag set theme_strength below scores in aggregate.
    """

    position_name: str
    semantic_role: str
    position_order: int
    card_name: str
    orientation: OrientationLiteral
    meaning_text: str
    themes: tuple[str, ...] = ()
    citation: Citation


class SuitClusterSummary(_Model):
    """2 or more drawn cards sharing one Suit (relationships.py Rule R1).
    Always at least 2 cards, by the same trigger relationships.py itself
    enforces (a "cluster" of fewer than 2 cards is not a cluster).
    """

    suit: SuitLiteral
    card_names: tuple[str, ...] = Field(min_length=2)
    citations: tuple[Citation, ...] = Field(min_length=2)


class Relationships(_Model):
    """Card-to-card structural relationships (Product Spec synthesis item
    3) and the suit/arcana-balance half of item 6, repeated patterns --
    relationships.py's own Rules R1 (same-suit clustering) and R2 (Major
    Arcana density), computed since the engine's foundation phase but
    never previously exposed on InterpretiveModel
    (Documentation/INTERPRETATION_RULES_DESIGN.md Section 7.1, Rules
    R3/R4: deferred pending "a new InterpretiveModel field... explicit
    rule... separately reviewed and approved" -- this field is exactly
    that approval, taking the schema-field resolution Section 7.1 itself
    named as one of its two open candidates, rather than the alternative
    it explicitly declined (folding this into `supporting_themes`)).

    Deliberately a plain enumeration of structural fact, not an
    interpretive claim -- this field's data must never feed
    `evidence_strength` scoring (Rule R4's specific, still-honored
    prohibition) or `supporting_themes` (Rule R3's), so a future reader
    does not mistake this exposure for having lifted either restriction.

    "Elements" (Wands=Fire, Cups=Water, etc.) and rank/numerological
    clustering are deliberately NOT included here -- see
    relationships.py and Documentation/INTERPRETATION_RULES_DESIGN.md
    Rule R5 for why (element correspondence data is a separate, entirely
    unused reference-data table; "meaningful" rank repetition has no
    approved taxonomy anywhere in this project's reviewed documentation).
    """

    same_suit_clusters: tuple[SuitClusterSummary, ...] = ()
    major_arcana_count: int
    minor_arcana_count: int


class ThemeStrength(_Model):
    """One theme tag's full support count across every drawn card's
    primary_themes + secondary_themes (meanings.py's score_theme_strength,
    Rule T1) -- the complete ranked list T1 already computes, exposed at
    full fidelity instead of truncated to central_issue + the top few
    supporting_themes. A theme with count >= 2 is, by definition,
    "reinforced" by more than one card (Product Spec synthesis item 4)
    and is one instance of "repeated thematic concepts" (item 6d) -- both
    are this same data, viewed from two angles; a consumer filters this
    one list rather than this schema exposing the same counts twice.
    """

    theme: str
    count: int
    citations: tuple[Citation, ...] = Field(min_length=1)


class InterpretiveModel(_Model):
    """One complete, deterministic interpretation of one Reading.

    See Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 4.1 for the
    field-by-field contract this mirrors exactly (Section 10.1-10.11's
    original 11 fields); `spread_name` through `theme_strength` and
    `deterministic_synthesis` below extend that contract with the
    additional structured synthesis data a later narrative/AI layer needs
    to describe what the drawn cards say TOGETHER, not merely what each
    means individually -- explicitly authorized as an additive schema
    extension, not a redesign of any existing field.
    """

    schema_version: str
    engine_version: str
    reference_data_version: str
    generated_at: datetime

    central_question: str
    spread_name: str
    spread_description: str | None = None
    card_interpretations: tuple[CardInterpretation, ...] = Field(min_length=1)
    relationships: Relationships
    theme_strength: tuple[ThemeStrength, ...] = ()

    central_issue: Explained[str]
    primary_tension: Explained[Tension] | None = None
    supporting_themes: tuple[Explained[str], ...] = ()
    trajectory: Explained[Trajectory] | None = None
    blocker: Explained[str] | None = None
    uncertainty: tuple[str, ...] = ()
    advice: Explained[str] | None = None
    clarification: Explained[str] | None = None
    contradictions: tuple[Contradiction, ...] = ()
    evidence_strength: EvidenceStrength

    deterministic_synthesis: Explained[str]
