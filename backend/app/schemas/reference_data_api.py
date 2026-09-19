"""Request/response schemas for the reference-data API (Step 41,
Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 4).

Covers Spreads (with SpreadPositions embedded), Cards, and Decks -- all
public, read-only, ownership-free reference content. No request schema
exists anywhere in this module; every route it backs is a plain GET with
at most one optional query parameter.

Deliberately minimal: excludes every interpretive-meaning field
(Card.base_meaning_upright/reversed, primary_themes/secondary_themes) --
not needed by a card *selector* UI, mirroring
app/schemas/reading_api.py::ReadingSummary's own "smallest useful
representation" discipline. The Reading Result screen's own need for
richer card content is already served by the interpretation response's
citations, not by this module.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import Arcana, SemanticRole, Suit


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields --
    the same discipline every other schema module in this project
    already applies, duplicated here (not imported) to keep this module
    independent, matching this project's existing per-resource schema
    module convention.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class SpreadPositionSummary(_Model):
    """One position within a Spread's embedded `positions` list.
    Excludes `spread_id` -- redundant once nested under its own Spread,
    matching ReadingSummary's own no-redundant-FK precedent.
    """

    id: UUID
    name: str
    description: str | None
    position_order: int
    semantic_role: SemanticRole
    required: bool


class SpreadSummary(_Model):
    """A Spread with its positions embedded directly -- one endpoint
    serves both the Layout Selection screen (which needs only
    `position_count`/`description`) and the Card Entry screen (which
    needs the full `positions` list), per
    Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 4's own
    reasoning for not splitting this into a separate list/detail pair.
    """

    id: UUID
    name: str
    description: str | None
    position_count: int
    allow_duplicate_cards: bool
    positions: list[SpreadPositionSummary]


class CardSummary(_Model):
    """The smallest representation sufficient for a searchable/
    filterable card selector -- id, display name, and the fields the
    Product Spec names as filter categories (arcana/suit), plus `rank`
    and `image_ref` for display. No interpretive-meaning field is
    included (see module docstring).
    """

    id: UUID
    name: str
    arcana: Arcana
    suit: Suit | None
    rank: str | None
    image_ref: str | None
    keywords: list[str]


class DeckSummary(_Model):
    """Deliberately neutral to Product Spec Q4 (deck-selection UI
    scope, unresolved) -- this shape serves the Settings "deck info"
    screen either way. See
    Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 4/10.
    """

    id: UUID
    name: str
    description: str | None
    is_default: bool
