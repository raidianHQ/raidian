"""Test-only helpers for building a Reading against the real, seeded
Rider-Waite-Smith reference data (see conftest.seeded_session).

Kept separate from tests/factories.py, whose own docstring scopes it to
minimal placeholder builders -- these helpers are specifically for
Interpretation Engine tests that need genuine card themes to exercise real
compound-theme rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Deck, Orientation, Reading, ReflectionSession, Spread, SpreadPosition

if TYPE_CHECKING:
    from app.models import User


def get_default_deck(session: Session) -> Deck:
    return session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()


def get_spread(session: Session, name: str) -> Spread:
    return session.scalars(select(Spread).where(Spread.name == name)).one()


def get_card(session: Session, deck: Deck, name: str) -> Card:
    return session.scalars(select(Card).where(Card.deck_id == deck.id, Card.name == name)).one()


def build_reading(
    session: Session,
    *,
    spread_name: str,
    draws: list[tuple[str, str, Orientation]],
    question: str = "What should I focus on right now?",
    question_domain: str | None = None,
    owner: "User | None" = None,
) -> Reading:
    """`draws` is a list of (position_name, card_name, orientation),
    assigned draw_order 1..N in the order given (which need not match the
    spread's own position_order -- exercising that distinction is the
    point in some tests).

    `owner` (Step 22) attaches the built Reading's ReflectionSession to the
    given User -- defaults to None (an unowned ReflectionSession), which
    preserves every pre-Step-22 caller's exact existing behavior unchanged.
    """
    deck = get_default_deck(session)
    spread = get_spread(session, spread_name)
    positions_by_name = {p.name: p for p in spread.positions}

    reflection_session = ReflectionSession(owner=owner)
    session.add(reflection_session)
    session.flush()

    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question=question,
        question_domain=question_domain,
    )
    session.add(reading)
    session.flush()

    for order, (position_name, card_name, orientation) in enumerate(draws, start=1):
        position: SpreadPosition = positions_by_name[position_name]
        card = get_card(session, deck, card_name)
        reading.add_card_draw(position=position, card=card, orientation=orientation, draw_order=order)

    session.flush()
    return reading
