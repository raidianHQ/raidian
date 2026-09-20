"""Unit tests for app/services/journal_service.py."""

from __future__ import annotations

import pytest

from app.models.journal_entry import JournalEntry
from app.services.journal_service import create_journal_entry, list_journal_entries
from tests.factories import make_deck, make_reading, make_spread


def _reading(session):
    return make_reading(session, make_spread(session), make_deck(session))


def test_create_journal_entry_persists_content_against_the_reading(db_session):
    reading = _reading(db_session)

    entry = create_journal_entry(db_session, reading, content="What stood out to me was the sense of patience.")

    assert entry.reading_id == reading.id
    assert entry.content == "What stood out to me was the sense of patience."
    assert entry.id is not None


def test_list_journal_entries_returns_them_oldest_first(db_session):
    reading = _reading(db_session)
    first = create_journal_entry(db_session, reading, content="First entry.")
    second = create_journal_entry(db_session, reading, content="Second entry.")

    entries = list_journal_entries(db_session, reading)

    assert [entry.id for entry in entries] == [first.id, second.id]


def test_list_journal_entries_is_scoped_to_the_reading(db_session):
    spread = make_spread(db_session)
    deck = make_deck(db_session)
    reading_a = make_reading(db_session, spread, deck)
    reading_b = make_reading(db_session, spread, deck)
    create_journal_entry(db_session, reading_a, content="Belongs to reading A.")

    assert len(list_journal_entries(db_session, reading_a)) == 1
    assert list_journal_entries(db_session, reading_b) == []


def test_list_journal_entries_returns_empty_list_when_none_exist(db_session):
    reading = _reading(db_session)

    assert list_journal_entries(db_session, reading) == []


def test_blank_content_is_rejected_at_the_model_layer(db_session):
    reading = _reading(db_session)

    with pytest.raises(ValueError):
        JournalEntry(reading=reading, content="   ")


def test_journal_entries_are_deleted_when_their_reading_is_deleted(db_session):
    reading = _reading(db_session)
    create_journal_entry(db_session, reading, content="Will be cascaded away.")
    db_session.flush()

    db_session.delete(reading)
    db_session.flush()

    remaining = db_session.query(JournalEntry).filter_by(reading_id=reading.id).all()
    assert remaining == []
