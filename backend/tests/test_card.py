import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Arcana, Card, Suit
from tests.factories import make_deck, make_major_card, make_minor_card


def test_card_definition_is_independent_of_any_reading(db_session):
    deck = make_deck(db_session)
    card = make_minor_card(db_session, deck, name="Ace of Cups", suit=Suit.CUPS, rank="ace")

    assert card.deck_id == deck.id
    assert card.arcana == Arcana.MINOR
    assert card.suit == Suit.CUPS
    assert card.card_draws == []  # no Reading has referenced it yet


def test_card_name_must_be_unique_within_a_deck(db_session):
    deck = make_deck(db_session)
    make_major_card(db_session, deck, name="The Fool")
    db_session.add(Card(deck=deck, name="The Fool", arcana=Arcana.MAJOR, rank="0"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_card_name_allowed_across_different_decks(db_session):
    deck_a = make_deck(db_session, name="Deck A")
    deck_b = make_deck(db_session, name="Deck B", is_default=False)

    make_major_card(db_session, deck_a, name="The Fool")
    make_major_card(db_session, deck_b, name="The Fool")  # should not raise

    db_session.flush()


def test_major_arcana_card_cannot_have_a_suit(db_session):
    deck = make_deck(db_session)
    db_session.add(Card(deck=deck, name="The Fool", arcana=Arcana.MAJOR, suit=Suit.CUPS, rank="0"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_minor_arcana_card_requires_a_suit(db_session):
    deck = make_deck(db_session)
    db_session.add(Card(deck=deck, name="Ace of Cups", arcana=Arcana.MINOR, suit=None, rank="ace"))

    with pytest.raises(IntegrityError):
        db_session.flush()
