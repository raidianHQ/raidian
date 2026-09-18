import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Card, CardDraw, DuplicateCardError, Orientation
from tests.factories import make_deck, make_major_card, make_minor_card, make_reading, make_spread


def _setup_reading(db_session, *, allow_duplicate_cards=False):
    spread = make_spread(
        db_session, allow_duplicate_cards=allow_duplicate_cards, position_names=("Past", "Present", "Future")
    )
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    return reading, spread, deck


def test_add_card_draw_records_position_card_orientation_and_order(db_session):
    reading, spread, deck = _setup_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")
    position = spread.positions[0]

    draw = reading.add_card_draw(
        position=position, card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()

    assert draw.reading_id == reading.id
    assert draw.position_id == position.id
    assert draw.card_id == card.id
    assert draw.orientation == Orientation.UPRIGHT
    assert draw.draw_order == 1
    assert draw.created_at is not None


def test_card_is_reference_data_independent_of_the_draw(db_session):
    """The same Card row must be reusable across multiple Readings."""
    deck = make_deck(db_session)
    card = make_major_card(db_session, deck, name="The Fool")

    spread_a = make_spread(db_session, name="Spread A", position_names=("Only",))
    reading_a = make_reading(db_session, spread_a, deck)
    reading_a.add_card_draw(
        position=spread_a.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )

    spread_b = make_spread(db_session, name="Spread B", position_names=("Only",))
    reading_b = make_reading(db_session, spread_b, deck)
    reading_b.add_card_draw(
        position=spread_b.positions[0], card=card, orientation=Orientation.REVERSED, draw_order=1
    )
    db_session.flush()

    assert len(card.card_draws) == 2


def test_duplicate_card_rejected_by_default(db_session):
    reading, spread, deck = _setup_reading(db_session, allow_duplicate_cards=False)
    card = make_major_card(db_session, deck, name="The Fool")

    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()

    with pytest.raises(DuplicateCardError):
        reading.add_card_draw(
            position=spread.positions[1], card=card, orientation=Orientation.REVERSED, draw_order=2
        )


def test_duplicate_card_allowed_when_spread_permits_it(db_session):
    reading, spread, deck = _setup_reading(db_session, allow_duplicate_cards=True)
    card = make_major_card(db_session, deck, name="The Fool")

    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    reading.add_card_draw(
        position=spread.positions[1], card=card, orientation=Orientation.REVERSED, draw_order=2
    )
    db_session.flush()

    assert len(reading.card_draws) == 2


def test_position_must_belong_to_the_readings_spread(db_session):
    reading, spread, deck = _setup_reading(db_session)
    other_spread = make_spread(db_session, name="Other Spread", position_names=("Somewhere",))
    card = make_major_card(db_session, deck, name="The Fool")

    with pytest.raises(ValueError):
        reading.add_card_draw(
            position=other_spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
        )


def test_card_must_belong_to_the_readings_deck(db_session):
    reading, spread, deck = _setup_reading(db_session)
    other_deck = make_deck(db_session, name="Other Deck", is_default=False)
    card = make_major_card(db_session, other_deck, name="The Fool")

    with pytest.raises(ValueError):
        reading.add_card_draw(
            position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
        )


def test_only_one_card_per_position_at_the_database_level(db_session):
    """Guards against a raw insert that bypasses Reading.add_card_draw."""
    reading, spread, deck = _setup_reading(db_session)
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


def test_draw_order_must_be_unique_within_a_reading(db_session):
    reading, spread, deck = _setup_reading(db_session)
    card_a = make_major_card(db_session, deck, name="The Fool")
    card_b = make_major_card(db_session, deck, name="The Magician")

    db_session.add(
        CardDraw(
            reading=reading, position=spread.positions[0], card=card_a,
            orientation=Orientation.UPRIGHT, draw_order=1,
        )
    )
    db_session.flush()
    db_session.add(
        CardDraw(
            reading=reading, position=spread.positions[1], card=card_b,
            orientation=Orientation.UPRIGHT, draw_order=1,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_draw_order_must_be_positive(db_session):
    reading, spread, deck = _setup_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")

    db_session.add(
        CardDraw(
            reading=reading, position=spread.positions[0], card=card,
            orientation=Orientation.UPRIGHT, draw_order=0,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_reading_cascades_to_its_card_draws(db_session):
    reading, spread, deck = _setup_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")
    draw = reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()
    draw_id = draw.id

    db_session.delete(reading)
    db_session.flush()

    assert db_session.get(CardDraw, draw_id) is None
    # Card is reference data and must survive the reading it was once drawn in.
    assert db_session.get(Card, card.id) is not None


def test_deleting_a_card_already_drawn_is_restricted(db_session):
    reading, spread, deck = _setup_reading(db_session)
    card = make_major_card(db_session, deck, name="The Fool")
    reading.add_card_draw(
        position=spread.positions[0], card=card, orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()

    db_session.delete(card)
    with pytest.raises(IntegrityError):
        db_session.flush()
