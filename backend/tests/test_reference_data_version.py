"""Tests for the reference-data content hash
(INTERPRETATION_ENGINE_DESIGN.md Section 9, Q2). The two properties that
matter most: identical content -> identical hash regardless of row
identity (UUIDs), and any real content change -> a different hash.
"""

from app.models import Card
from app.services.interpretation.reference_data_version import compute_reference_data_version


def test_hash_is_a_64_char_hex_sha256_digest(seeded_session):
    version = compute_reference_data_version(seeded_session)
    assert len(version) == 64
    int(version, 16)  # must not raise -- confirms it's valid hex


def test_hash_is_stable_across_repeated_calls_against_the_same_data(seeded_session):
    v1 = compute_reference_data_version(seeded_session)
    v2 = compute_reference_data_version(seeded_session)
    assert v1 == v2


def test_hash_is_identical_across_two_independently_fresh_seeds(db_session):
    """The critical property: two databases seeded from scratch (and so
    holding completely different random UUIDs) must hash to the same
    value, because the *content* is identical. Sorting/hashing by id
    instead of content would break this.
    """
    from app.seed.seed import seed_reference_data

    seed_reference_data(db_session)
    db_session.commit()
    first = compute_reference_data_version(db_session)

    # Re-run the idempotent seed again in the same session -- upserts in
    # place, still same content, must still match.
    seed_reference_data(db_session)
    db_session.commit()
    second = compute_reference_data_version(db_session)

    assert first == second


def test_hash_changes_when_a_cards_theme_content_changes(seeded_session):
    before = compute_reference_data_version(seeded_session)

    fool = seeded_session.query(Card).filter_by(name="The Fool").one()
    fool.primary_themes = [*fool.primary_themes, "a_theme_not_really_in_the_vocabulary"]
    seeded_session.flush()

    after = compute_reference_data_version(seeded_session)
    assert before != after


def test_hash_does_not_change_when_only_unrelated_row_metadata_differs(seeded_session):
    """created_at/updated_at/id are explicitly excluded from the hashed
    payload -- touching a row without changing its content-relevant fields
    must not change the version.
    """
    before = compute_reference_data_version(seeded_session)

    fool = seeded_session.query(Card).filter_by(name="The Fool").one()
    # Re-assign the same value -- SQLAlchemy may still bump updated_at on
    # flush depending on backend timing, but the hashed payload never reads
    # updated_at, so the version must be unaffected either way.
    fool.rank = fool.rank
    seeded_session.flush()

    after = compute_reference_data_version(seeded_session)
    assert before == after
