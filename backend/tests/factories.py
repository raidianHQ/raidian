"""Small, explicit builders for test fixtures -- not a general-purpose factory
framework. Each function does the minimum needed to get a valid, flushed row.
"""

from sqlalchemy.orm import Session

from app.models import (
    Arcana,
    Card,
    Deck,
    DrawMethod,
    Reading,
    ReflectionSession,
    SemanticRole,
    Spread,
    SpreadPosition,
    Suit,
)


def make_deck(session: Session, name: str = "Rider-Waite-Smith", is_default: bool = True) -> Deck:
    deck = Deck(name=name, is_default=is_default)
    session.add(deck)
    session.flush()
    return deck


def make_major_card(session: Session, deck: Deck, name: str = "The Fool", rank: str = "0") -> Card:
    card = Card(deck=deck, name=name, arcana=Arcana.MAJOR, suit=None, rank=rank)
    session.add(card)
    session.flush()
    return card


def make_minor_card(
    session: Session,
    deck: Deck,
    name: str = "Ace of Cups",
    suit: Suit = Suit.CUPS,
    rank: str = "ace",
) -> Card:
    card = Card(deck=deck, name=name, arcana=Arcana.MINOR, suit=suit, rank=rank)
    session.add(card)
    session.flush()
    return card


def make_spread(
    session: Session,
    name: str = "Three Card",
    allow_duplicate_cards: bool = False,
    position_names: tuple[str, ...] = ("Past", "Present", "Future"),
) -> Spread:
    spread = Spread(name=name, allow_duplicate_cards=allow_duplicate_cards)
    session.add(spread)
    session.flush()
    for order, position_name in enumerate(position_names, start=1):
        session.add(
            SpreadPosition(
                spread=spread,
                name=position_name,
                position_order=order,
                semantic_role=SemanticRole.GENERAL,
            )
        )
    session.flush()
    return spread


def make_reading(
    session: Session,
    spread: Spread,
    deck: Deck,
    question: str = "What should I focus on right now?",
    draw_method: DrawMethod = DrawMethod.PHYSICAL,
) -> Reading:
    reflection_session = ReflectionSession()
    session.add(reflection_session)
    session.flush()

    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question=question,
        draw_method=draw_method,
    )
    session.add(reading)
    session.flush()
    return reading
