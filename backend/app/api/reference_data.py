"""HTTP transport layer for reference data: Spreads (with
SpreadPositions embedded), Cards, and Decks (Step 41,
Documentation/REFERENCE_DATA_CORS_DESIGN.md).

Thin routes only -- each queries its own model(s) directly (there is no
orchestration layer for a plain reference-data read, the same
discipline app/api/reading.py's own GET /readings History route already
established) and maps ORM rows to response schemas via a small,
module-local helper per resource.

Deliberately public -- no Depends(get_current_user) anywhere in this
module. Step 40's design (Documentation/REFERENCE_DATA_CORS_DESIGN.md
Section 5) left this open; public was the behavior authorized for this
step's implementation. None of Spread/SpreadPosition/Card/Deck carries
an ownership column, so no get_owned_reading-style boundary applies
here regardless of that choice.

Deliberately does not implement pagination or server-side search for
Cards -- the seeded dataset (78 Cards, 3 Spreads, 1 Deck, confirmed live
in Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 2) is small
enough for a single full-list response, searched/filtered client-side.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.card import Card
from app.models.deck import Deck
from app.models.enums import Arcana, Suit
from app.models.spread import Spread
from app.schemas.reference_data_api import (
    CardSummary,
    DeckSummary,
    SpreadPositionSummary,
    SpreadSummary,
)

router = APIRouter(tags=["reference-data"])

_DECK_NOT_FOUND = "Deck not found"

_ARCANA_ORDER = {Arcana.MAJOR: 0, Arcana.MINOR: 1}
_SUIT_ORDER = {suit: index for index, suit in enumerate(Suit)}
_MINOR_RANK_ORDER = {
    "ace": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "page": 11,
    "knight": 12,
    "queen": 13,
    "king": 14,
}


def _card_sort_key(card: Card) -> tuple[int, int, int]:
    """Card.rank is a free-form string ("0".."21" for Major Arcana, a
    rank word for Minor Arcana) -- not lexicographically sortable into a
    natural order at the database level (the string "10" sorts before
    "2"; "king" sorts before "two"). This key interprets the existing
    values correctly, entirely in application code, without adding any
    new column.
    """
    suit_order = _SUIT_ORDER.get(card.suit, -1) if card.suit is not None else -1
    rank_order = int(card.rank) if card.arcana == Arcana.MAJOR else _MINOR_RANK_ORDER.get(card.rank, 99)
    return (_ARCANA_ORDER[card.arcana], suit_order, rank_order)


def _to_spread_summary(spread: Spread) -> SpreadSummary:
    return SpreadSummary(
        id=spread.id,
        name=spread.name,
        description=spread.description,
        position_count=spread.position_count,
        allow_duplicate_cards=spread.allow_duplicate_cards,
        positions=[
            SpreadPositionSummary(
                id=position.id,
                name=position.name,
                description=position.description,
                position_order=position.position_order,
                semantic_role=position.semantic_role,
                required=position.required,
            )
            for position in spread.positions
        ],
    )


def _to_card_summary(card: Card) -> CardSummary:
    return CardSummary(
        id=card.id,
        name=card.name,
        arcana=card.arcana,
        suit=card.suit,
        rank=card.rank,
        image_ref=card.image_ref,
        keywords=card.keywords,
    )


def _to_deck_summary(deck: Deck) -> DeckSummary:
    return DeckSummary(
        id=deck.id,
        name=deck.name,
        description=deck.description,
        is_default=deck.is_default,
    )


@router.get(
    "/spreads",
    response_model=list[SpreadSummary],
    summary="List available Spreads",
    description=(
        "Every seeded Spread, with its SpreadPositions embedded, "
        "ordered by name. Supports the New Reading -- Layout Selection "
        "screen. See Documentation/REFERENCE_DATA_CORS_DESIGN.md "
        "Section 4."
    ),
)
def list_spreads_route(session: Session = Depends(get_db)) -> list[SpreadSummary]:
    spreads = session.scalars(select(Spread).order_by(Spread.name)).all()
    return [_to_spread_summary(spread) for spread in spreads]


@router.get(
    "/cards",
    response_model=list[CardSummary],
    summary="List available Cards",
    description=(
        "Every Card in the given deck (or the seeded default deck if "
        "deck_id is omitted), in a fixed, natural arcana/suit/rank "
        "order. Supports the Card Entry searchable/filterable card "
        "selector -- search/filtering itself is a client-side concern "
        "over this full list. See "
        "Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 4."
    ),
    responses={404: {"description": _DECK_NOT_FOUND}},
)
def list_cards_route(
    deck_id: UUID | None = None, session: Session = Depends(get_db)
) -> list[CardSummary]:
    if deck_id is not None:
        deck = session.get(Deck, deck_id)
        if deck is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DECK_NOT_FOUND)
    else:
        deck = session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()

    cards = session.scalars(select(Card).where(Card.deck_id == deck.id)).all()
    return [_to_card_summary(card) for card in sorted(cards, key=_card_sort_key)]


@router.get(
    "/decks",
    response_model=list[DeckSummary],
    summary="List available Decks",
    description=(
        "Every seeded Deck. Supports the Settings screen's deck-info "
        "display; deliberately neutral to whether deck-switching UI is "
        "ever built (Product Spec Q4, unresolved -- see "
        "Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 10)."
    ),
)
def list_decks_route(session: Session = Depends(get_db)) -> list[DeckSummary]:
    decks = session.scalars(select(Deck).order_by(Deck.name)).all()
    return [_to_deck_summary(deck) for deck in decks]
