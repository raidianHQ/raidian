import pytest
from sqlalchemy.exc import IntegrityError

from app.models import DrawMethod, Reading, ReadingStatus, ReflectionSession
from tests.factories import make_deck, make_reading, make_spread


def test_reading_defaults(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck, question="Where is my career heading?")

    assert reading.draw_method == DrawMethod.PHYSICAL  # physical is the default draw method
    assert reading.status == ReadingStatus.DRAFTING
    assert reading.question_domain is None
    assert reading.created_at is not None
    assert reading.updated_at is not None


def test_reading_is_the_tarot_portion_of_a_reflection_session(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    assert isinstance(reading.reflection_session, ReflectionSession)
    assert reading.reflection_session.reading is reading


def test_reflection_session_reading_is_one_to_one(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)

    second_reading = Reading(
        reflection_session=reading.reflection_session,
        spread=spread,
        deck=deck,
        question="A second reading in the same session?",
    )
    db_session.add(second_reading)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_reflection_session_cascades_to_its_reading(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck)
    reflection_session = reading.reflection_session
    reading_id = reading.id

    db_session.delete(reflection_session)
    db_session.flush()

    assert db_session.get(Reading, reading_id) is None


def test_question_cannot_be_blank(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)

    with pytest.raises(ValueError):
        make_reading(db_session, spread, deck, question="   ")


def test_digital_draw_method_is_representable_even_though_unimplemented(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    assert reading.draw_method == DrawMethod.DIGITAL


def test_deleting_a_spread_still_in_use_is_restricted(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    make_reading(db_session, spread, deck)

    db_session.delete(spread)
    with pytest.raises(IntegrityError):
        db_session.flush()
