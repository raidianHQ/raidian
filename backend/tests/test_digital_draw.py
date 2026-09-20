"""Service-level tests for Digital Draw:
app/services/reading_service.py::select_digital_cards() (pure card
selection) and record_digital_draw() (validation + persistence via the
same Reading.add_card_draw() manual entry already uses). Mirrors
tests/test_card_draw.py's model/service-level style (db_session +
tests/factories.py, no HTTP layer) -- API-level tests for
POST /readings/{reading_id}/draws/digital live in
tests/test_api_reading.py's own "Digital Draw" section instead, alongside
every other Reading-resource route.

See Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 8.2.
"""

from __future__ import annotations

import secrets
import uuid
from random import Random

import pytest
from sqlalchemy import select

import app.services.reading_service as reading_service_module
from app.models import Card, CardDraw, DrawMethod, Orientation, ReadingStatus
from app.models.exceptions import (
    DeckNotFoundError,
    InsufficientCardsForDigitalDrawError,
    ReadingAlreadyDrawnError,
    ReadingNotDigitalError,
    ReadingNotDraftingError,
    SpreadNotFoundError,
)
from app.services.reading_service import record_digital_draw, select_digital_cards
from tests.factories import make_deck, make_major_card, make_reading, make_spread


def _setup(
    db_session,
    *,
    allow_duplicate_cards: bool = False,
    position_names: tuple[str, ...] = ("Past", "Present", "Future"),
    num_cards: int = 3,
) -> tuple:
    spread = make_spread(db_session, allow_duplicate_cards=allow_duplicate_cards, position_names=position_names)
    deck = make_deck(db_session)
    cards = [make_major_card(db_session, deck, name=f"Card {i}", rank=str(i)) for i in range(num_cards)]
    return spread, deck, cards


# =====================================================================================
# select_digital_cards() -- pure card selection
# =====================================================================================


def test_select_digital_cards_returns_one_assignment_per_position(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert len(assignments) == 3


def test_select_digital_cards_positions_match_the_spread_in_position_order(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert [p.id for p, _, _ in assignments] == [p.id for p in spread.positions]


def test_select_digital_cards_cards_belong_to_the_deck(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    deck_card_ids = {c.id for c in cards}

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert all(card.id in deck_card_ids for _, card, _ in assignments)


def test_select_digital_cards_are_unique_when_spread_disallows_duplicates(db_session):
    spread, deck, cards = _setup(db_session, allow_duplicate_cards=False, num_cards=3)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    card_ids = [card.id for _, card, _ in assignments]
    assert len(card_ids) == len(set(card_ids))
    assert set(card_ids) == {c.id for c in cards}


def test_select_digital_cards_allows_duplicates_when_spread_permits_it(db_session):
    """One Card, three Positions, duplicates permitted -- a duplicate is
    the only possible outcome, making this deterministic rather than
    probabilistic.
    """
    spread, deck, cards = _setup(db_session, allow_duplicate_cards=True, num_cards=1)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert len(assignments) == 3
    assert all(card.id == cards[0].id for _, card, _ in assignments)


def test_select_digital_cards_raises_when_deck_has_fewer_cards_than_positions(db_session):
    spread, deck, cards = _setup(db_session, allow_duplicate_cards=False, num_cards=2)

    with pytest.raises(InsufficientCardsForDigitalDrawError):
        select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)


def test_select_digital_cards_exact_card_count_match_succeeds(db_session):
    """The boundary case: exactly as many cards as positions, duplicates
    disallowed -- must succeed (not off-by-one reject a valid draw).
    """
    spread, deck, cards = _setup(db_session, allow_duplicate_cards=False, num_cards=3)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert len(assignments) == 3


def test_select_digital_cards_orientations_are_valid_values(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)

    assignments = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert all(o in (Orientation.UPRIGHT, Orientation.REVERSED) for _, _, o in assignments)


def test_select_digital_cards_defaults_to_a_systemrandom_source(db_session, monkeypatch):
    """Section 8.2's "CSPRNG-backed shuffle" requirement: the default rng,
    when none is injected, must be secrets.SystemRandom -- not the
    default (Mersenne Twister) random module state.
    """
    spread, deck, cards = _setup(db_session, num_cards=3)
    created: list[object] = []
    real_system_random = secrets.SystemRandom

    class _SpyRandom(real_system_random):
        def __init__(self):
            super().__init__()
            created.append(self)

    monkeypatch.setattr(reading_service_module.secrets, "SystemRandom", _SpyRandom)

    select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id)

    assert len(created) == 1


def test_select_digital_cards_accepts_a_custom_rng_for_deterministic_tests(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)

    first = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id, rng=Random(42))
    second = select_digital_cards(db_session, deck_id=deck.id, spread_id=spread.id, rng=Random(42))

    assert [c.id for _, c, _ in first] == [c.id for _, c, _ in second]
    assert [o for _, _, o in first] == [o for _, _, o in second]


def test_select_digital_cards_raises_for_a_nonexistent_spread(db_session):
    deck = make_deck(db_session)
    make_major_card(db_session, deck)

    with pytest.raises(SpreadNotFoundError):
        select_digital_cards(db_session, deck_id=deck.id, spread_id=uuid.uuid4())


def test_select_digital_cards_raises_for_a_nonexistent_deck(db_session):
    spread = make_spread(db_session)

    with pytest.raises(DeckNotFoundError):
        select_digital_cards(db_session, deck_id=uuid.uuid4(), spread_id=spread.id)


# =====================================================================================
# record_digital_draw() -- validation + persistence
# =====================================================================================


def test_record_digital_draw_creates_a_card_draw_per_position(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    draws = record_digital_draw(db_session, reading)

    assert len(draws) == 3
    assert {d.position_id for d in draws} == {p.id for p in spread.positions}


def test_record_digital_draw_persists_the_card_draws(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    record_digital_draw(db_session, reading)

    persisted = db_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).scalars().all()
    assert len(persisted) == 3


def test_record_digital_draw_advances_reading_to_spread_complete(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    record_digital_draw(db_session, reading)

    assert reading.status == ReadingStatus.SPREAD_COMPLETE


def test_record_digital_draw_requires_digital_draw_method(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.PHYSICAL)

    with pytest.raises(ReadingNotDigitalError):
        record_digital_draw(db_session, reading)

    assert reading.card_draws == []
    assert reading.status == ReadingStatus.DRAFTING


def test_record_digital_draw_requires_drafting_status(db_session):
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)
    record_digital_draw(db_session, reading)
    assert reading.status == ReadingStatus.SPREAD_COMPLETE

    with pytest.raises(ReadingNotDraftingError):
        record_digital_draw(db_session, reading)


def test_record_digital_draw_rejects_a_reading_with_an_existing_card_draw(db_session):
    """Covers the edge case reachable only because the manual
    record_card_draw() path does not itself check draw_method: a DIGITAL,
    still-DRAFTING reading that already has one CardDraw (only 1 of 3
    required positions filled) must reject Digital Draw rather than
    attempt to top it up.
    """
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)
    reading.add_card_draw(
        position=spread.positions[0], card=cards[0], orientation=Orientation.UPRIGHT, draw_order=1
    )
    db_session.flush()
    assert reading.status == ReadingStatus.DRAFTING

    with pytest.raises(ReadingAlreadyDrawnError):
        record_digital_draw(db_session, reading)

    assert len(reading.card_draws) == 1  # unchanged


def test_record_digital_draw_is_atomic_when_card_selection_fails(db_session):
    """Insufficient cards fails inside select_digital_cards(), before any
    CardDraw is added -- the earliest possible failure point, and the
    simplest proof that a rejected call leaves the reading untouched.
    """
    spread, deck, cards = _setup(
        db_session, allow_duplicate_cards=False, num_cards=2, position_names=("A", "B", "C")
    )
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    with pytest.raises(InsufficientCardsForDigitalDrawError):
        record_digital_draw(db_session, reading)

    assert reading.card_draws == []
    assert reading.status == ReadingStatus.DRAFTING


def test_record_digital_draw_leaves_no_partial_rows_on_a_later_failure(db_session, monkeypatch):
    """Forces Reading.add_card_draw() to fail on the *second* of three
    calls -- after selection has already succeeded and the first draw has
    already been appended in memory -- proving the all-or-nothing
    guarantee holds even once persistence has begun, since
    record_digital_draw() calls session.flush() exactly once, after every
    add_card_draw() call in its loop, never per-call.
    """
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    real_add_card_draw = reading.add_card_draw
    calls = {"count": 0}

    def _flaky_add_card_draw(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated failure on the second position")
        return real_add_card_draw(*args, **kwargs)

    monkeypatch.setattr(reading, "add_card_draw", _flaky_add_card_draw)

    with pytest.raises(RuntimeError):
        record_digital_draw(db_session, reading)

    db_session.rollback()
    persisted = db_session.execute(select(CardDraw).where(CardDraw.reading_id == reading.id)).scalars().all()
    assert persisted == []


def test_record_digital_draw_respects_allow_duplicate_cards(db_session):
    spread, deck, cards = _setup(db_session, allow_duplicate_cards=True, num_cards=1)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    draws = record_digital_draw(db_session, reading)

    assert len(draws) == 3
    assert all(d.card_id == cards[0].id for d in draws)


def test_record_digital_draw_card_is_reference_data_independent_of_the_draw(db_session):
    """The Cards select_digital_cards() picks remain ordinary, reusable
    reference data -- unaffected by, and not consumed by, the draw.
    """
    spread, deck, cards = _setup(db_session, num_cards=3)
    reading = make_reading(db_session, spread, deck, draw_method=DrawMethod.DIGITAL)

    record_digital_draw(db_session, reading)

    assert db_session.get(Card, cards[0].id) is not None
