"""Resolves a Reading's ORM graph into a small, immutable, deterministically
ordered structure every pipeline stage reads from.

This is the one place that touches the ORM directly -- every stage module
downstream operates only on ReadingContext/DrawContext, never on
app.models objects, so stages stay pure and DB-independent (testable with
plain fixtures, per Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.enums import Arcana, Orientation, SemanticRole, Suit
from app.models.reading import Reading


@dataclass(frozen=True)
class DrawContext:
    """One drawn card, fully resolved, with everything a pipeline stage
    needs to reason about it or cite it.
    """

    card_draw_id: UUID
    card_id: UUID
    card_name: str
    arcana: Arcana
    suit: Suit | None
    orientation: Orientation
    meaning_text: str

    position_id: UUID
    position_name: str
    semantic_role: SemanticRole
    position_order: int

    # As stored (human-curated priority order from the reference-data YAML
    # content) -- never re-sorted alphabetically, which would discard that
    # ordering. Deduplication/ranking across cards happens in meanings.py,
    # not here.
    primary_themes: tuple[str, ...]
    secondary_themes: tuple[str, ...]

    @property
    def all_themes(self) -> tuple[str, ...]:
        """primary_themes followed by secondary_themes, as stored, with
        duplicates removed but relative order preserved. Order is not
        semantically meaningless here (primary before secondary) so it must
        not be replaced with a sorted-by-alphabet union.
        """
        seen: dict[str, None] = {}
        for theme in (*self.primary_themes, *self.secondary_themes):
            seen.setdefault(theme, None)
        return tuple(seen.keys())


@dataclass(frozen=True)
class ReadingContext:
    """Everything the pipeline needs for one Reading, immutable and
    deterministically ordered.

    draws is ordered by SpreadPosition.position_order (the spread's own
    structural sequence) -- deliberately NOT CardDraw.draw_order, which is
    a data-entry/physical-draw sequence with no structural meaning of its
    own (INTERPRETATION_ENGINE_DESIGN.md Section 2.2).
    """

    reading_id: UUID
    question: str
    question_domain: str | None
    spread_id: UUID
    spread_name: str
    spread_description: str | None
    draws: tuple[DrawContext, ...]

    def draws_with_role(self, role: SemanticRole) -> tuple[DrawContext, ...]:
        return tuple(d for d in self.draws if d.semantic_role == role)


def build_reading_context(reading: Reading) -> ReadingContext:
    """Pure transformation: Reading (+ its loaded relationships) -> ReadingContext.

    Requires reading.card_draws, each draw's .card and .position, to already
    be loaded/accessible (a normal SQLAlchemy session with default lazy
    loading satisfies this; no eager-loading strategy is mandated here).
    """
    draws = []
    for draw in reading.card_draws:
        card = draw.card
        position = draw.position

        meaning_text = (
            card.base_meaning_upright
            if draw.orientation == Orientation.UPRIGHT
            else card.base_meaning_reversed
        )

        draws.append(
            DrawContext(
                card_draw_id=draw.id,
                card_id=card.id,
                card_name=card.name,
                arcana=card.arcana,
                suit=card.suit,
                orientation=draw.orientation,
                meaning_text=meaning_text or "",
                position_id=position.id,
                position_name=position.name,
                semantic_role=position.semantic_role,
                position_order=position.position_order,
                primary_themes=tuple(card.primary_themes),
                secondary_themes=tuple(card.secondary_themes),
            )
        )

    draws.sort(key=lambda d: d.position_order)

    return ReadingContext(
        reading_id=reading.id,
        question=reading.question,
        question_domain=reading.question_domain,
        spread_id=reading.spread_id,
        spread_name=reading.spread.name,
        spread_description=reading.spread.description,
        draws=tuple(draws),
    )
