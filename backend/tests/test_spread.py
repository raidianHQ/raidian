import pytest
from sqlalchemy.exc import IntegrityError

from app.models import SemanticRole, Spread, SpreadPosition
from tests.factories import make_spread


def test_spread_position_count_is_derived_not_stored(db_session):
    spread = make_spread(db_session, position_names=("Situation", "Advice"))

    assert spread.position_count == 2
    assert [p.name for p in spread.positions] == ["Situation", "Advice"]


def test_spread_contains_no_actual_cards(db_session):
    spread = make_spread(db_session)

    # A Spread is a definition only; nothing on it should reference a Card.
    assert not hasattr(spread, "cards")


def test_spread_name_must_be_unique(db_session):
    make_spread(db_session, name="Three Card")
    db_session.add(Spread(name="Three Card"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_position_order_must_be_unique_within_a_spread(db_session):
    spread = make_spread(db_session, position_names=("Past",))
    db_session.add(
        SpreadPosition(
            spread=spread, name="Present", position_order=1, semantic_role=SemanticRole.GENERAL
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_position_order_must_be_positive(db_session):
    spread = make_spread(db_session, position_names=())
    db_session.add(
        SpreadPosition(
            spread=spread, name="Bad Position", position_order=0, semantic_role=SemanticRole.GENERAL
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_spread_cascades_to_its_positions(db_session):
    spread = make_spread(db_session, position_names=("Only Position",))
    position_id = spread.positions[0].id

    db_session.delete(spread)
    db_session.flush()

    assert db_session.get(SpreadPosition, position_id) is None


def test_duplicate_cards_disallowed_by_default(db_session):
    spread = make_spread(db_session)
    assert spread.allow_duplicate_cards is False
