import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Deck
from tests.factories import make_deck, make_minor_card


def test_deck_has_timestamps_and_defaults(db_session):
    deck = make_deck(db_session, name="Rider-Waite-Smith", is_default=True)

    assert deck.id is not None
    assert deck.created_at is not None
    assert deck.updated_at is not None
    assert deck.is_default is True


def test_deck_name_must_be_unique(db_session):
    make_deck(db_session, name="Rider-Waite-Smith")
    db_session.add(Deck(name="Rider-Waite-Smith", is_default=False))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_deck_cascades_to_its_cards(db_session):
    deck = make_deck(db_session)
    card = make_minor_card(db_session, deck)
    card_id = card.id

    db_session.delete(deck)
    db_session.flush()

    assert db_session.get(type(card), card_id) is None
