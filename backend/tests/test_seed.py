"""Verifies the seed process actually loads the reference data into the
database correctly, and that it is safe/idempotent to run repeatedly.
"""

from app.models import Card, CardCorrespondence, Deck, Spread, SpreadPosition
from app.models.enums import Arcana, Suit
from app.seed.seed import seed_reference_data


def test_seed_creates_exactly_78_rws_cards(db_session):
    seed_reference_data(db_session)

    cards = db_session.query(Card).all()
    assert len(cards) == 78


def test_seed_creates_22_major_and_56_minor(db_session):
    seed_reference_data(db_session)

    majors = db_session.query(Card).filter_by(arcana=Arcana.MAJOR).all()
    minors = db_session.query(Card).filter_by(arcana=Arcana.MINOR).all()
    assert len(majors) == 22
    assert len(minors) == 56


def test_seed_creates_fourteen_cards_per_suit(db_session):
    seed_reference_data(db_session)

    for suit in Suit:
        count = db_session.query(Card).filter_by(suit=suit).count()
        assert count == 14, f"{suit} had {count} cards"


def test_seed_creates_the_default_deck(db_session):
    summary = seed_reference_data(db_session)

    deck = db_session.query(Deck).one()
    assert deck.name == "Rider-Waite-Smith"
    assert deck.is_default is True
    assert deck is summary.deck


def test_all_card_names_unique_within_the_deck(db_session):
    seed_reference_data(db_session)

    names = [card.name for card in db_session.query(Card).all()]
    assert len(names) == len(set(names))


def test_seeded_cards_have_all_required_content_populated(db_session):
    seed_reference_data(db_session)

    for card in db_session.query(Card).all():
        assert card.rank
        assert card.image_ref
        assert card.base_meaning_upright
        assert card.base_meaning_reversed
        assert card.keywords
        assert card.primary_themes
        assert card.secondary_themes


def test_expected_spreads_exist(db_session):
    seed_reference_data(db_session)

    names = {spread.name for spread in db_session.query(Spread).all()}
    assert names == {"Single Card", "Three Card", "Celtic Cross"}


def test_expected_spread_positions_exist(db_session):
    seed_reference_data(db_session)

    counts = {
        spread.name: len(spread.positions) for spread in db_session.query(Spread).all()
    }
    assert counts == {"Single Card": 1, "Three Card": 3, "Celtic Cross": 10}


def test_celtic_cross_exercises_required_semantic_roles(db_session):
    seed_reference_data(db_session)

    celtic_cross = db_session.query(Spread).filter_by(name="Celtic Cross").one()
    roles = {position.semantic_role.value for position in celtic_cross.positions}

    required_roles = {"situation", "recent_past", "influence_blocker", "near_future", "advice", "advice_clarifier"}
    assert required_roles.issubset(roles)


def test_seed_process_is_repeatable(db_session):
    """Running the seed twice against the same database must not create
    duplicate rows or raise -- this is the idempotency contract seed.py
    documents.
    """
    seed_reference_data(db_session)
    seed_reference_data(db_session)  # second run must be a no-op in effect

    assert db_session.query(Deck).count() == 1
    assert db_session.query(Card).count() == 78
    assert db_session.query(Spread).count() == 3
    assert db_session.query(SpreadPosition).count() == 1 + 3 + 10


def test_reseeding_updates_content_in_place(db_session):
    """A content correction (edit YAML, re-run seed) should update the
    existing row rather than creating a second one.
    """
    seed_reference_data(db_session)

    fool = db_session.query(Card).filter_by(name="The Fool").one()
    original_id = fool.id
    fool.base_meaning_upright = "temporarily overwritten for this test"
    db_session.flush()

    seed_reference_data(db_session)  # should restore the real content, same row

    fool_again = db_session.query(Card).filter_by(name="The Fool").one()
    assert fool_again.id == original_id
    assert fool_again.base_meaning_upright != "temporarily overwritten for this test"


# --- Card Correspondences -------------------------------------------------


def test_seed_creates_78_correspondence_records(db_session):
    seed_reference_data(db_session)

    assert db_session.query(CardCorrespondence).count() == 78


def test_every_card_has_exactly_one_correspondence(db_session):
    seed_reference_data(db_session)

    for card in db_session.query(Card).all():
        assert card.correspondence is not None
        assert card.correspondence.card_id == card.id


def test_correspondence_element_matches_traditional_suit_element(db_session):
    seed_reference_data(db_session)

    expected = {Suit.WANDS: "fire", Suit.CUPS: "water", Suit.SWORDS: "air", Suit.PENTACLES: "earth"}
    for suit, element in expected.items():
        cards = db_session.query(Card).filter_by(suit=suit).all()
        assert len(cards) == 14
        for card in cards:
            assert card.correspondence.element == element


def test_strength_and_judgement_corrections_applied_in_db(db_session):
    seed_reference_data(db_session)

    strength = db_session.query(Card).filter_by(name="Strength").one()
    judgement = db_session.query(Card).filter_by(name="Judgement").one()

    assert strength.correspondence.zodiac_signs == ["leo"]
    assert judgement.correspondence.zodiac_signs == ["scorpio"]


def test_deleting_a_card_cascades_to_its_correspondence(db_session):
    seed_reference_data(db_session)

    fool = db_session.query(Card).filter_by(name="The Fool").one()
    correspondence_id = fool.correspondence.id

    db_session.delete(fool)
    db_session.flush()

    assert db_session.get(CardCorrespondence, correspondence_id) is None


def test_correspondence_seeding_is_repeatable(db_session):
    seed_reference_data(db_session)
    seed_reference_data(db_session)

    assert db_session.query(CardCorrespondence).count() == 78
