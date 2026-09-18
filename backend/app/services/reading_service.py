"""Reading creation business logic (Step 27). See
Documentation/READING_CREATION_API_DESIGN.md Section 9,
Documentation/READING_CREATION_OWNERSHIP_DESIGN.md Section 7.4.

A single, narrow service function -- mirrors
app/services/auth_service.py::register_user()'s exact shape (lookup
existing rows, construct new ones, flush, never commit). Deliberately not
a model method (unlike Reading.add_card_draw()/mark_saved()): this
operation needs Session access to validate a client-supplied spread_id/
deck_id actually exist, which no session-free model method can do.
Deliberately not part of app/services/reading_orchestration.py either --
that module is scoped strictly to combining database access with the
Interpretation Engine and Narrative Layer; Reading creation touches
neither.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deck import Deck
from app.models.enums import DrawMethod
from app.models.exceptions import DeckNotFoundError, SpreadNotFoundError
from app.models.reading import Reading
from app.models.reflection_session import ReflectionSession
from app.models.spread import Spread
from app.models.user import User


def create_reading(
    session: Session,
    owner: User,
    *,
    spread_id: UUID,
    question: str,
    question_domain: str | None,
    draw_method: DrawMethod,
    deck_id: UUID | None = None,
) -> Reading:
    """Creates a new, owned Reading in its default DRAFTING status.

    `owner` is required (not `User | None`) -- a structural guard against
    ever constructing an owner-less ReflectionSession from this path
    (Documentation/READING_CREATION_API_DESIGN.md Section 12). Raises
    SpreadNotFoundError / DeckNotFoundError if the referenced row doesn't
    exist; never creates a Spread or Deck itself -- both are pre-seeded
    reference data (app/seed/seed.py). Blank/over-length question and
    over-length question_domain are already rejected by
    app/schemas/reading_api.py::ReadingCreateRequest before this function
    is ever called -- this function relies on Reading's own
    `@validates("question")` only as a final, defense-in-depth guarantee,
    not as this service's primary validation mechanism.

    Never flushes fewer than once per constructed row, and never commits
    or rolls back -- the caller (the get_db request boundary,
    app/db/session.py) controls the transaction, exactly as every other
    service in this project already does.
    """
    spread = session.get(Spread, spread_id)
    if spread is None:
        raise SpreadNotFoundError(f"spread {spread_id} does not exist")

    if deck_id is not None:
        deck = session.get(Deck, deck_id)
        if deck is None:
            raise DeckNotFoundError(f"deck {deck_id} does not exist")
    else:
        # Exactly one Deck is ever seeded today (app/seed/seed.py::seed_deck()
        # loads a single RWS_DECK_DIR, with is_default: true in its own
        # reference-data file) -- confirmed by direct repository inspection,
        # not assumed. See Documentation/READING_CREATION_API_DESIGN.md
        # Section 5.
        deck = session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()

    reflection_session = ReflectionSession(owner=owner)
    session.add(reflection_session)
    session.flush()

    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question=question,
        question_domain=question_domain,
        draw_method=draw_method,
    )
    session.add(reading)
    session.flush()
    return reading
