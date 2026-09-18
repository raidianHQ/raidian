"""Tests for the Reading/Draw lifecycle behavior implemented in Step 16
(Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md Section 5/7):
automatic DRAFTING -> SPREAD_COMPLETE transition on the final required
draw, and CardDraw immutability once a Reading has left DRAFTING.

Uses tests/factories.py's minimal placeholder builders (not the real
seeded reference data) -- these tests are about status/CardDraw
lifecycle mechanics, not card themes, exactly matching test_card_draw.py's
own existing convention.

Interpretation-lifecycle compatibility (interpreting a SPREAD_COMPLETE
reading; reinterpreting an INTERPRETED or SAVED reading) is deliberately
NOT re-tested here -- it is already covered by
test_reading_orchestration.py's test_spread_complete_transitions_to_interpreted,
test_interpreted_stays_interpreted_on_reinterpretation, and
test_saved_reading_remains_saved_after_reinterpretation, all of which
continue to pass unchanged against this step's implementation.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CardDraw, DuplicateCardError, Orientation, Reading, ReadingStatus
from app.models.exceptions import ReadingNotDraftingError
from tests.factories import make_deck, make_major_card, make_reading, make_spread


def _setup_three_position_reading(db_session):
    spread = make_spread(db_session, name="Three Card", position_names=("Past", "Present", "Future"))
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    return reading, spread, deck


# --- Completion ------------------------------------------------------------------


def test_incomplete_draw_leaves_status_drafting(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")

    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()

    assert reading.status == ReadingStatus.DRAFTING
    assert reading.is_spread_complete is False


def test_incomplete_reading_stays_incomplete_and_drafting(db_session):
    """Two of three required positions filled -- existing incomplete-reading
    behavior (is_spread_complete False, status untouched) remains intact."""
    reading, spread, deck = _setup_three_position_reading(db_session)
    card_a = make_major_card(db_session, deck, name="The Fool")
    card_b = make_major_card(db_session, deck, name="The Magician")

    reading.add_card_draw(
        position=spread.positions[0], card=card_a, orientation=Orientation.UPRIGHT, draw_order=1
    )
    reading.add_card_draw(
        position=spread.positions[1], card=card_b, orientation=Orientation.UPRIGHT, draw_order=2
    )
    db_session.flush()

    assert reading.is_spread_complete is False
    assert reading.status == ReadingStatus.DRAFTING


def test_final_required_draw_transitions_to_spread_complete(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    cards = [
        make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(3)
    ]

    for order, (position, card) in enumerate(zip(spread.positions, cards), start=1):
        reading.add_card_draw(
            position=position, card=card, orientation=Orientation.UPRIGHT, draw_order=order
        )
    db_session.flush()

    assert reading.is_spread_complete is True
    assert reading.status == ReadingStatus.SPREAD_COMPLETE


def test_completion_occurs_exactly_when_required_positions_are_covered(db_session):
    """Status must remain DRAFTING after every draw except the last, and
    become SPREAD_COMPLETE only at the exact moment the last required
    position is filled -- not before, not lazily later.
    """
    reading, spread, deck = _setup_three_position_reading(db_session)
    cards = [
        make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(3)
    ]

    reading.add_card_draw(
        position=spread.positions[0], card=cards[0], orientation=Orientation.UPRIGHT, draw_order=1
    )
    assert reading.status == ReadingStatus.DRAFTING

    reading.add_card_draw(
        position=spread.positions[1], card=cards[1], orientation=Orientation.UPRIGHT, draw_order=2
    )
    assert reading.status == ReadingStatus.DRAFTING

    reading.add_card_draw(
        position=spread.positions[2], card=cards[2], orientation=Orientation.UPRIGHT, draw_order=3
    )
    assert reading.status == ReadingStatus.SPREAD_COMPLETE


def test_status_remains_spread_complete_once_reached(db_session):
    """Idempotent in the sense the design requires: once SPREAD_COMPLETE,
    the state holds -- including across a flush/commit/expire round trip.
    """
    reading, spread, deck = _setup_three_position_reading(db_session)
    cards = [
        make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(3)
    ]
    for order, (position, card) in enumerate(zip(spread.positions, cards), start=1):
        reading.add_card_draw(
            position=position, card=card, orientation=Orientation.UPRIGHT, draw_order=order
        )
    db_session.commit()

    reading_id = reading.id
    db_session.expire_all()
    reloaded = db_session.get(Reading, reading_id)

    assert reloaded.status == ReadingStatus.SPREAD_COMPLETE
    assert reloaded.is_spread_complete is True


# --- Immutability ------------------------------------------------------------------


def test_add_card_draw_rejected_when_spread_complete(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    cards = [
        make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(4)
    ]
    for order, (position, card) in enumerate(zip(spread.positions, cards), start=1):
        reading.add_card_draw(
            position=position, card=card, orientation=Orientation.UPRIGHT, draw_order=order
        )
    db_session.flush()
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    with pytest.raises(ReadingNotDraftingError):
        reading.add_card_draw(
            position=spread.positions[0], card=cards[3], orientation=Orientation.REVERSED, draw_order=4
        )


def test_add_card_draw_rejected_when_interpreted(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")
    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()
    reading.status = ReadingStatus.INTERPRETED
    db_session.flush()

    other_card = make_major_card(db_session, deck, name="The Magician")
    with pytest.raises(ReadingNotDraftingError):
        reading.add_card_draw(
            position=spread.positions[1], card=other_card, orientation=Orientation.UPRIGHT, draw_order=2
        )


def test_add_card_draw_rejected_when_saved(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")
    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()
    reading.status = ReadingStatus.SAVED
    db_session.flush()

    other_card = make_major_card(db_session, deck, name="The Magician")
    with pytest.raises(ReadingNotDraftingError):
        reading.add_card_draw(
            position=spread.positions[1], card=other_card, orientation=Orientation.UPRIGHT, draw_order=2
        )


# --- Existing protections remain intact --------------------------------------------


def test_duplicate_card_still_rejected_while_drafting(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")

    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()

    with pytest.raises(DuplicateCardError):
        reading.add_card_draw(
            position=spread.positions[1], card=card, orientation=Orientation.REVERSED, draw_order=2
        )
    assert reading.status == ReadingStatus.DRAFTING  # rejected draw must not affect status


def test_duplicate_position_still_rejected_by_the_database_while_drafting(db_session):
    """Guards against a raw insert bypassing add_card_draw -- unchanged
    from test_card_draw.py's existing coverage, re-confirmed here in the
    lifecycle-focused context (the new leading guard must not interfere
    with this DB-level protection)."""
    reading, spread, deck = _setup_three_position_reading(db_session)
    card_a = make_major_card(db_session, deck, name="The Fool")
    card_b = make_major_card(db_session, deck, name="The Magician")
    position = spread.positions[0]

    db_session.add(
        CardDraw(reading=reading, position=position, card=card_a, orientation=Orientation.UPRIGHT, draw_order=1)
    )
    db_session.flush()
    db_session.add(
        CardDraw(reading=reading, position=position, card=card_b, orientation=Orientation.UPRIGHT, draw_order=2)
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


# --- Transaction rollback -----------------------------------------------------------


def test_rollback_of_the_completing_draw_undoes_both_the_draw_and_the_transition(db_session):
    reading, spread, deck = _setup_three_position_reading(db_session)
    card_a = make_major_card(db_session, deck, name="Card A")
    card_b = make_major_card(db_session, deck, name="Card B")
    card_c = make_major_card(db_session, deck, name="Card C")

    reading.add_card_draw(
        position=spread.positions[0], card=card_a, orientation=Orientation.UPRIGHT, draw_order=1
    )
    reading.add_card_draw(
        position=spread.positions[1], card=card_b, orientation=Orientation.UPRIGHT, draw_order=2
    )
    db_session.commit()  # commit the first two (incomplete) draws + the reading itself
    reading_id = reading.id

    reading.add_card_draw(
        position=spread.positions[2], card=card_c, orientation=Orientation.UPRIGHT, draw_order=3
    )
    assert reading.status == ReadingStatus.SPREAD_COMPLETE  # completed, but not yet committed

    db_session.rollback()

    reloaded = db_session.get(Reading, reading_id)
    assert reloaded.status == ReadingStatus.DRAFTING  # rolled back
    assert len(reloaded.card_draws) == 2  # the third (completing) draw is gone
