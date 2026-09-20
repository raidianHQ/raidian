"""Validates the Scripture reference-data YAML content and its loader-time
guardrails, independent of the database -- mirrors
test_reference_data_loader.py's own "catch content problems without
seeding anything" discipline, applied to the optional Scriptural
Reflection layer (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section
15).
"""

from __future__ import annotations

import pytest

from app.seed.loader import (
    APPROVED_SCRIPTURE_TRANSLATIONS,
    BIBLE_BOOKS,
    ReferenceDataError,
    load_scripture_reference_definitions,
    validate_scripture_reference_definitions,
)

_REAL_THEME_VOCABULARY = {"fear", "anxiety", "patience", "relationships", "grief", "hope", "uncertainty"}


def _entry(**overrides) -> dict:
    defaults = dict(
        theme="fear",
        book="2 Timothy",
        chapter=1,
        verse_start=7,
        verse_end=None,
        reference_display="2 Timothy 1:7",
        translation="KJV",
        context_note="A note about the passage.",
        reflection_connection="A connection to the theme.",
    )
    defaults.update(overrides)
    return defaults


# --- The real seed content -----------------------------------------------------


def test_the_real_seed_file_loads_and_validates():
    entries = load_scripture_reference_definitions()
    validate_scripture_reference_definitions(entries)
    assert len(entries) >= 1


def test_every_seeded_theme_exists_in_the_real_theme_vocabulary():
    from app.seed.loader import load_theme_vocabulary

    vocabulary = load_theme_vocabulary()
    entries = load_scripture_reference_definitions()
    for entry in entries:
        assert entry["theme"] in vocabulary


def test_every_seeded_translation_is_approved():
    entries = load_scripture_reference_definitions()
    for entry in entries:
        assert entry["translation"] in APPROVED_SCRIPTURE_TRANSLATIONS


def test_no_seeded_entry_contains_passage_text_fields():
    """A structural guardrail against ever silently gaining a `text` or
    `passage`/`verse_text` field -- Section 15.1's licensing constraint
    ("Do not embed copyrighted Bible translation text in the MVP") is
    enforced by this dataset's own shape never carrying such a field at
    all, not merely by convention.
    """
    entries = load_scripture_reference_definitions()
    forbidden_keys = {"text", "passage", "verse_text", "passage_text", "quote"}
    for entry in entries:
        assert forbidden_keys.isdisjoint(entry.keys())


# --- Validation guardrails (invalid/unapproved references rejected) ------------


def test_rejects_a_theme_not_in_the_canonical_vocabulary():
    with pytest.raises(ReferenceDataError, match="theme"):
        validate_scripture_reference_definitions(
            [_entry(theme="not_a_real_theme")], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_rejects_an_unapproved_translation():
    with pytest.raises(ReferenceDataError, match="translation"):
        validate_scripture_reference_definitions(
            [_entry(translation="NIV")], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_accepts_every_approved_translation():
    for translation in APPROVED_SCRIPTURE_TRANSLATIONS:
        validate_scripture_reference_definitions(
            [_entry(translation=translation)], theme_vocabulary=_REAL_THEME_VOCABULARY
        )  # must not raise


def test_rejects_an_unrecognized_book_name():
    with pytest.raises(ReferenceDataError, match="book"):
        validate_scripture_reference_definitions(
            [_entry(book="Book of Fake Wisdom")], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_accepts_every_canonical_book_name():
    for book in BIBLE_BOOKS:
        validate_scripture_reference_definitions(
            [_entry(book=book)], theme_vocabulary=_REAL_THEME_VOCABULARY
        )  # must not raise


def test_rejects_a_non_positive_chapter():
    with pytest.raises(ReferenceDataError, match="chapter"):
        validate_scripture_reference_definitions(
            [_entry(chapter=0)], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_rejects_a_non_positive_verse_start():
    with pytest.raises(ReferenceDataError, match="verse_start"):
        validate_scripture_reference_definitions(
            [_entry(verse_start=0)], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_rejects_a_verse_end_before_verse_start():
    with pytest.raises(ReferenceDataError, match="verse_end"):
        validate_scripture_reference_definitions(
            [_entry(verse_start=10, verse_end=5)], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_accepts_a_null_verse_end_for_a_single_verse_reference():
    validate_scripture_reference_definitions(
        [_entry(verse_start=18, verse_end=None)], theme_vocabulary=_REAL_THEME_VOCABULARY
    )  # must not raise


def test_rejects_a_missing_required_text_field():
    with pytest.raises(ReferenceDataError, match="context_note"):
        entry = _entry()
        del entry["context_note"]
        validate_scripture_reference_definitions([entry], theme_vocabulary=_REAL_THEME_VOCABULARY)


def test_rejects_a_blank_required_text_field():
    with pytest.raises(ReferenceDataError, match="reflection_connection"):
        validate_scripture_reference_definitions(
            [_entry(reflection_connection="   ")], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_rejects_duplicate_entries_with_the_same_natural_key():
    with pytest.raises(ReferenceDataError, match="duplicate"):
        validate_scripture_reference_definitions(
            [_entry(), _entry()], theme_vocabulary=_REAL_THEME_VOCABULARY
        )


def test_allows_the_same_theme_to_have_multiple_distinct_references():
    validate_scripture_reference_definitions(
        [
            _entry(),
            _entry(book="Isaiah", chapter=41, verse_start=10, reference_display="Isaiah 41:10"),
        ],
        theme_vocabulary=_REAL_THEME_VOCABULARY,
    )  # must not raise


def test_reports_every_problem_at_once_not_just_the_first():
    with pytest.raises(ReferenceDataError) as exc_info:
        validate_scripture_reference_definitions(
            [_entry(theme="not_real", translation="NIV", chapter=-1)],
            theme_vocabulary=_REAL_THEME_VOCABULARY,
        )
    problems = exc_info.value.problems
    assert len(problems) >= 3
