"""Reading creation and CardDraw-recording business logic (Step 27;
record_card_draw() added Step 32; select_digital_cards()/
record_digital_draw() added for Digital Draw). See
Documentation/READING_CREATION_API_DESIGN.md Section 9,
Documentation/READING_CREATION_OWNERSHIP_DESIGN.md Section 7.4,
Documentation/CARDDRAW_API_DESIGN.md Section 7,
Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 8.2.

Narrow service functions -- mirror
app/services/auth_service.py::register_user()'s exact shape (lookup
existing rows, construct/mutate, flush, never commit). Deliberately not
model methods (unlike Reading.add_card_draw()/mark_saved(), which
record_card_draw() itself delegates to for the actual lifecycle
mutation): both operations here need Session access to validate
client-supplied foreign IDs (spread_id/deck_id, or position_id/card_id)
actually exist, which no session-free model method can do. Deliberately
not part of app/services/reading_orchestration.py either -- that module
is scoped strictly to combining database access with the Interpretation
Engine and Narrative Layer; neither Reading creation nor CardDraw
recording touches either. Deliberately kept in this one file rather than
a separate draw_service.py -- no concrete reason in the current
repository justifies that split yet (Documentation/CARDDRAW_API_DESIGN.md
Section 7).
"""

from __future__ import annotations

import secrets
from random import Random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.card_draw import CardDraw
from app.models.deck import Deck
from app.models.enums import DrawMethod, Orientation, ReadingStatus
from app.models.exceptions import (
    CardNotFoundError,
    DeckNotFoundError,
    InsufficientCardsForDigitalDrawError,
    PositionAlreadyDrawnError,
    ReadingAlreadyDrawnError,
    ReadingNotDeletableError,
    ReadingNotDigitalError,
    ReadingNotDraftingError,
    SpreadNotFoundError,
    SpreadPositionNotFoundError,
)
from app.models.reading import Reading
from app.models.reflection_session import ReflectionSession
from app.models.spread import Spread
from app.models.spread_position import SpreadPosition
from app.models.user import User

_ORIENTATIONS: tuple[Orientation, ...] = (Orientation.UPRIGHT, Orientation.REVERSED)


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


def _is_position_already_drawn_violation(exc: IntegrityError) -> bool:
    """Recognizes the card_draws uq_card_draws_reading_id_position_id
    violation specifically -- the database's authoritative data-integrity
    invariant for duplicate positions -- distinct from the sibling
    uq_card_draws_reading_id_draw_order constraint. Mirrors
    app/services/auth_service.py::_is_duplicate_email_violation()'s exact
    technique: matches both SQLite's message ("UNIQUE constraint failed:
    card_draws.reading_id, card_draws.position_id") and PostgreSQL's
    (constraint name "uq_card_draws_reading_id_position_id" embedded in
    the message), both containing "position_id".

    Under a genuine concurrent same-position race, a single insert can
    violate both constraints at once, and SQLite has been observed to
    report the draw_order constraint instead -- this function correctly
    returns False in that case, so the raw IntegrityError propagates
    rather than being misreported as PositionAlreadyDrawnError. This is
    an accepted single-writer limitation, not a defect in this function
    (Documentation/CARDDRAW_CONCURRENCY_RECONCILIATION.md); the position
    uniqueness invariant itself is unaffected either way.
    """
    message = str(exc.orig if exc.orig is not None else exc).lower()
    return "position_id" in message and ("unique" in message or "duplicate" in message)


def record_card_draw(
    session: Session,
    reading: Reading,
    *,
    position_id: UUID,
    card_id: UUID,
    orientation: Orientation,
) -> CardDraw:
    """Records a single CardDraw against `reading` (Step 32,
    Documentation/CARDDRAW_API_DESIGN.md Section 7).

    `reading` is already-resolved and already-owned (the caller passes
    the object app.api.dependencies.get_owned_reading produced) -- this
    function performs no ownership check of its own, mirroring
    save_reading_route()'s own pattern of taking a Reading directly
    rather than a reading_id.

    Raises SpreadPositionNotFoundError if position_id does not reference
    an existing SpreadPosition, or references one that does not belong to
    reading.spread (the two cases collapse into one error and one 404,
    Documentation/CARDDRAW_API_DESIGN.md Section 6). Raises
    CardNotFoundError under the same collapsing rule for card_id/
    reading.deck. Raises PositionAlreadyDrawnError if the position already
    has a CardDraw recorded AND the reading is still DRAFTING -- detected
    by an in-memory pre-check against reading.card_draws (already loaded,
    no extra query), which reliably catches the ordinary, sequential
    case; under a genuine concurrent race this exception is not
    guaranteed, since the same insert may instead surface as a raw
    IntegrityError -- an accepted single-writer limitation, not a defect
    (see _is_position_already_drawn_violation()'s own docstring). The
    pre-check is deliberately gated on `reading.status == DRAFTING` (not
    unconditional): every real, fully-required spread reaches
    SPREAD_COMPLETE with literally every position already filled, so an
    unconditional pre-check would always fire first for a non-DRAFTING
    reading and mask the more accurate ReadingNotDraftingError underneath
    it -- gating the pre-check lets add_card_draw()'s own DRAFTING guard
    remain the one and only place that decides and raises for that case,
    with this function duplicating no part of that decision.

    draw_order is computed here, server-side, as
    max(existing draw_order) + 1 (or 1 if this is the first draw) --
    never accepted from the caller (Documentation/CARDDRAW_API_DESIGN.md
    Section 4.3), the same reasoning already applied to
    Interpretation.sequence's own server-side _next_sequence().

    All lifecycle mutation (the DRAFTING-only guard, the duplicate-card
    rule, the SPREAD_COMPLETE transition) is delegated entirely to
    Reading.add_card_draw() -- this function duplicates none of it, only
    resolving foreign IDs and computing draw_order beforehand.

    Never commits or rolls back -- the caller (the get_db request
    boundary, app/db/session.py) controls the transaction, exactly as
    create_reading() above and every other service in this project
    already does.
    """
    position = session.get(SpreadPosition, position_id)
    if position is None or position.spread_id != reading.spread_id:
        raise SpreadPositionNotFoundError(
            f"position {position_id} does not exist on reading {reading.id}'s spread"
        )

    card = session.get(Card, card_id)
    if card is None or card.deck_id != reading.deck_id:
        raise CardNotFoundError(f"card {card_id} does not exist in reading {reading.id}'s deck")

    if reading.status == ReadingStatus.DRAFTING and any(
        existing.position_id == position.id for existing in reading.card_draws
    ):
        raise PositionAlreadyDrawnError(
            f"position {position_id} has already been drawn in reading {reading.id}"
        )

    next_draw_order = max((existing.draw_order for existing in reading.card_draws), default=0) + 1

    draw = reading.add_card_draw(
        position=position, card=card, orientation=orientation, draw_order=next_draw_order
    )
    try:
        session.flush()
    except IntegrityError as exc:
        if not _is_position_already_drawn_violation(exc):
            raise
        raise PositionAlreadyDrawnError(
            f"position {position_id} has already been drawn in reading {reading.id}"
        ) from exc
    return draw


def delete_reading(session: Session, reading: Reading) -> None:
    """Permanently deletes `reading` and every persisted row beneath it
    (CardDraw, Interpretation, and -- one level further -- AINarrative/
    ScripturalReflection under Interpretation, plus JournalEntry) --
    Delete Saved Reading, Raidian Reading Lifecycle improvements.

    Raises ReadingNotDeletableError if `reading.status` is not SAVED --
    Delete Saved Reading is scoped to saved readings only; checked first,
    before anything is touched. `reading` is already-resolved and
    already-owned (the caller passes the object
    app.api.dependencies.get_owned_reading produced), exactly mirroring
    record_card_draw()/record_digital_draw()'s own contract -- this
    function performs no ownership check of its own.

    Deletes `reading.reflection_session`, not `reading` directly: Reading
    carries no owner column of its own (ReflectionSession.owner_id is the
    ownership anchor -- see ReflectionSession's own docstring), so
    deleting only the Reading row would leave an orphaned, ownerless
    ReflectionSession behind with nothing beneath it. Every table this
    needs to remove is already wired for exactly this via existing
    relationships/database constraints, so nothing new is introduced
    here: ReflectionSession.reading cascades at the ORM level
    (cascade="all, delete-orphan"), and CardDraw/Interpretation/
    JournalEntry (ondelete="CASCADE" on their reading_id column) and
    AINarrative/ScripturalReflection (ondelete="CASCADE" on their
    interpretation_id column) all cascade at the database level -- one
    delete removes the entire tree.

    Never commits or rolls back -- the caller (the get_db request
    boundary, app/db/session.py) controls the transaction, exactly as
    every other function in this module already does.
    """
    if reading.status != ReadingStatus.SAVED:
        raise ReadingNotDeletableError(
            f"reading {reading.id} is not SAVED (status={reading.status.value}); "
            "only a saved reading can be deleted"
        )
    session.delete(reading.reflection_session)
    session.flush()


def select_digital_cards(
    session: Session,
    *,
    deck_id: UUID,
    spread_id: UUID,
    rng: Random | None = None,
) -> list[tuple[SpreadPosition, Card, Orientation]]:
    """Pure Digital Draw card selection -- a Fisher-Yates shuffle (via
    `rng.shuffle`) of `deck_id`'s Cards, sampled without replacement and
    assigned one per `spread_id`'s Positions in position_order (or, if
    the Spread's `allow_duplicate_cards` is set, sampled independently
    with replacement instead).

    Deliberately takes only `deck_id`/`spread_id` -- no Reading, no
    question, no interpretation output -- so there is no parameter
    through which reading content could bias, or be biased by, this
    selection, by construction
    (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 8.2: "the
    digital-draw service function's signature should take only deck_id
    and layout_id ... and nothing else"). Orientation (upright/reversed)
    is determined here too, independently per position -- Digital Draw
    replaces the physical act of drawing entirely, including the
    orientation a physical draw would have produced; unlike Physical
    (Section 8.1, "the app is a recorder, not a participant in the
    draw"), here the app is the participant.

    `rng` defaults to `secrets.SystemRandom()` -- a CSPRNG-backed source,
    not the default Mersenne Twister -- per the same Section 8.2
    requirement ("a standard unbiased CSPRNG-backed shuffle ... not a
    naive repeated-random-choice loop susceptible to bias at scale").
    Overridable only for deterministic tests.

    Raises SpreadNotFoundError/DeckNotFoundError if either id is
    invalid (unreachable through the current API, since
    record_digital_draw() below always calls this with an
    already-resolved Reading's own spread_id/deck_id; kept as
    defense-in-depth, the same discipline Reading.validate_question()
    applies behind its own schema-level guard). Raises
    InsufficientCardsForDigitalDrawError if the Deck has fewer Cards
    than the Spread has Positions and duplicates are not allowed.
    """
    spread = session.get(Spread, spread_id)
    if spread is None:
        raise SpreadNotFoundError(f"spread {spread_id} does not exist")

    deck = session.get(Deck, deck_id)
    if deck is None:
        raise DeckNotFoundError(f"deck {deck_id} does not exist")

    positions = list(spread.positions)
    cards = list(deck.cards)

    if not spread.allow_duplicate_cards and len(cards) < len(positions):
        raise InsufficientCardsForDigitalDrawError(
            f"deck {deck_id} has {len(cards)} card(s), fewer than the "
            f"{len(positions)} position(s) required by spread {spread_id}, "
            "and this spread does not allow duplicate cards"
        )

    active_rng: Random = rng if rng is not None else secrets.SystemRandom()

    if spread.allow_duplicate_cards:
        selected_cards = [active_rng.choice(cards) for _ in positions]
    else:
        shuffled = list(cards)
        active_rng.shuffle(shuffled)
        selected_cards = shuffled[: len(positions)]

    orientations = [active_rng.choice(_ORIENTATIONS) for _ in positions]

    return list(zip(positions, selected_cards, orientations))


def record_digital_draw(
    session: Session,
    reading: Reading,
    *,
    rng: Random | None = None,
) -> list[CardDraw]:
    """Performs a complete Digital Draw against `reading`: selects a card
    (and orientation) for every position of its Spread via
    select_digital_cards() above, then records all of them via
    Reading.add_card_draw() -- the same lifecycle mutation (DRAFTING
    guard, duplicate-card rule, auto-advance to SPREAD_COMPLETE) manual
    entry already goes through, reused here without duplication.

    `reading` is already-resolved and already-owned (the caller passes
    the object app.api.dependencies.get_owned_reading produced), exactly
    mirroring record_card_draw()'s own contract above.

    Raises ReadingNotDigitalError if reading.draw_method is not DIGITAL.
    Raises ReadingNotDraftingError if reading.status is not DRAFTING.
    Raises ReadingAlreadyDrawnError if reading already has one or more
    CardDraw rows -- Digital Draw is whole-spread and atomic, never a
    top-up of a partially-filled reading. All three checks run before any
    card is selected or any row is added, so a rejected call leaves
    `reading` and the session completely untouched.

    All Positions are drawn in one pass, entirely in memory, before a
    single `session.flush()` call -- either every CardDraw is created
    together or (on any error, including a duplicate-card violation from
    an allow_duplicate_cards=False spread that happens to reshuffle a
    repeat -- structurally impossible here since selection already
    samples without replacement, but guarded via the same
    Reading.add_card_draw() rule regardless) none is, matching
    record_card_draw()'s own "never commits or rolls back; the caller
    controls the transaction" discipline.
    """
    if reading.draw_method != DrawMethod.DIGITAL:
        raise ReadingNotDigitalError(
            f"reading {reading.id} has draw_method={reading.draw_method.value}; "
            "digital draw requires draw_method=digital"
        )
    if reading.status != ReadingStatus.DRAFTING:
        raise ReadingNotDraftingError(
            f"reading {reading.id} is not DRAFTING (status={reading.status.value}); "
            "digital draw can only be performed while a reading is drafting"
        )
    if reading.card_draws:
        raise ReadingAlreadyDrawnError(
            f"reading {reading.id} already has {len(reading.card_draws)} card draw(s) recorded; "
            "digital draw can only be performed against a reading with none"
        )

    assignments = select_digital_cards(
        session, deck_id=reading.deck_id, spread_id=reading.spread_id, rng=rng
    )

    draws = [
        reading.add_card_draw(position=position, card=card, orientation=orientation, draw_order=order)
        for order, (position, card, orientation) in enumerate(assignments, start=1)
    ]
    session.flush()
    return draws
