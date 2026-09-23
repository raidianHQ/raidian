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


def test_discernment_and_clarity_have_real_seeded_references():
    """Guards the specific fix for the reported "Discernment produces no
    Scripture" bug: `discernment` and `clarity` must each have at least
    one real, verifiable seeded reference (a recognized canonical book
    name -- see BIBLE_BOOKS -- not a placeholder), not merely exist as
    theme_vocabulary tags with nothing mapped to them.
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in ("discernment", "clarity"):
        theme_entries = by_theme.get(theme, [])
        assert theme_entries, f"expected at least one seeded reference for theme {theme!r}"
        for entry in theme_entries:
            assert entry["book"] in BIBLE_BOOKS
            assert entry["reference_display"]


_FIRST_COVERAGE_EXPANSION_THEMES = (
    "new_beginnings", "authority", "stability", "discipline", "mentorship",
    "emotional_connection", "compassion", "nurturing", "joy", "contentment",
    "loss", "mystery", "inner_strength", "courage", "solitude", "choice",
    "fairness", "accountability", "truth", "honest_communication", "conflict",
    "hardship", "burden", "exhaustion", "transformation", "letting_go",
    "revelation", "reckoning", "renewal", "healing", "rest", "vigilance",
    "completion", "wholeness", "abundance", "skill_and_craft", "diligence",
    "generosity", "community",
)
"""The 39 themes added in the first Scripture coverage expansion batch
(Raidian Reading Lifecycle improvements -- Scripture coverage audit),
mirroring _FIRST_COVERAGE_EXPANSION_THEMES's own role: every one of these
must have at least one real, verifiable seeded reference, each still
capped at _MAX_REFLECTIONS-worth of genuinely distinct approved rows
(never inflated just to hit the up-to-3 target)."""


def test_first_coverage_expansion_themes_have_real_seeded_references():
    """Every theme added in the first coverage expansion batch has at
    least one real, verifiable seeded reference (a recognized canonical
    book name, a non-empty reference_display) -- mirrors
    test_discernment_and_clarity_have_real_seeded_references()'s own
    guard, applied to the larger batch.
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in _FIRST_COVERAGE_EXPANSION_THEMES:
        theme_entries = by_theme.get(theme, [])
        assert theme_entries, f"expected at least one seeded reference for theme {theme!r}"
        for entry in theme_entries:
            assert entry["book"] in BIBLE_BOOKS
            assert entry["reference_display"]
            assert entry["translation"] == "KJV"


def test_first_coverage_expansion_themes_never_exceed_three_references():
    """"Up to 3 is a target, not a requirement" -- no theme in the new
    batch was padded with a fourth reference just to reach the cap, and
    several themes deliberately have fewer than 3 (documented as the
    batch's own honest outcome, not an oversight).
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in _FIRST_COVERAGE_EXPANSION_THEMES:
        assert len(by_theme.get(theme, [])) <= 3


_ORIGINAL_SEED_THEMES = {
    "fear", "anxiety", "patience", "relationships", "grief",
    "hope", "uncertainty", "discernment", "clarity",
}
"""The initial 9-theme seed set, factored out so both the first and
second coverage-expansion count guards below can reference the same
baseline."""


_SECOND_COVERAGE_EXPANSION_TIER1_THEMES = (
    "willpower", "ambition", "breakthrough", "structure", "tradition",
    "hidden_knowledge", "introspection", "indecision", "upheaval",
    "self_evaluation", "legacy", "material_security", "reliability",
    "entrapment", "memory", "creativity", "opportunity", "risk_taking",
    "focus", "determination", "attachment", "recovery", "collaboration",
    "authenticity",
)
"""The 24 "Strong / obvious fit" themes from the second Scripture
coverage expansion batch (the audit's own remaining Tier 1)."""


_SECOND_COVERAGE_EXPANSION_TIER2_THEMES = (
    "intuition", "inner_guidance", "adaptability", "strategy", "illusion",
    "endings", "transition", "cycles", "potential", "exploration",
    "openness", "control", "recognition", "fulfillment", "vitality",
    "romantic_pursuit", "curiosity",
)
"""The 17 "Moderate / plausible fit" themes from the second Scripture
coverage expansion batch (the audit's own remaining Tier 2) -- each
seeded with a reference whose reflection_connection explicitly frames
the passage as related but not a literal synonym for the theme."""


_TIER_3_UNMAPPED_THEMES = (
    "belief_systems", "balance", "integration", "values_alignment",
    "communication", "diplomacy", "practicality", "resourcefulness",
    "self_sufficiency", "patterns", "restriction", "evasion",
    "spontaneity", "assertiveness", "momentum", "idealism", "sensuality",
    "manifestation",
)
"""The 18 "Weak / abstract fit" themes the audit recommended leaving
unmapped -- guarded here so a future edit can't silently map one of
these without it being a deliberate, reviewed decision."""


def test_second_coverage_expansion_tier1_themes_have_real_seeded_references():
    """Mirrors test_first_coverage_expansion_themes_have_real_seeded_references()
    for the second batch's Tier 1 (Strong) themes.
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in _SECOND_COVERAGE_EXPANSION_TIER1_THEMES:
        theme_entries = by_theme.get(theme, [])
        assert theme_entries, f"expected at least one seeded reference for theme {theme!r}"
        for entry in theme_entries:
            assert entry["book"] in BIBLE_BOOKS
            assert entry["reference_display"]
            assert entry["translation"] == "KJV"


def test_second_coverage_expansion_tier2_themes_have_real_seeded_references():
    """Mirrors the Tier 1 guard above for the second batch's Tier 2
    (Moderate) themes -- these still require a real, verifiable
    reference even though their framing is more cautious.
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in _SECOND_COVERAGE_EXPANSION_TIER2_THEMES:
        theme_entries = by_theme.get(theme, [])
        assert theme_entries, f"expected at least one seeded reference for theme {theme!r}"
        for entry in theme_entries:
            assert entry["book"] in BIBLE_BOOKS
            assert entry["reference_display"]
            assert entry["translation"] == "KJV"


def test_second_coverage_expansion_themes_never_exceed_three_references():
    """"Up to 3 is a target, not a requirement" -- applied to the second
    batch (Tier 1 + Tier 2 combined). Several themes deliberately have
    fewer than 3, documented as the batch's own honest outcome.
    """
    entries = load_scripture_reference_definitions()
    by_theme: dict[str, list[dict]] = {}
    for entry in entries:
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in _SECOND_COVERAGE_EXPANSION_TIER1_THEMES + _SECOND_COVERAGE_EXPANSION_TIER2_THEMES:
        assert len(by_theme.get(theme, [])) <= 3


def test_tier_3_themes_remain_unmapped():
    """The audit's "Weak / abstract fit" themes were deliberately left
    without direct Scripture coverage -- this must stay true unless a
    future change makes that a deliberate, separately-reviewed decision
    (this test would then need an equally deliberate update, not a
    silent pass).
    """
    entries = load_scripture_reference_definitions()
    themes = {entry["theme"] for entry in entries}
    assert themes.isdisjoint(_TIER_3_UNMAPPED_THEMES)


def test_seeded_theme_count_reflects_the_first_coverage_expansion():
    """A coarse, hard-to-fake regression guard: the seed file, after the
    first coverage expansion batch alone, covered the original 9 themes
    plus that batch's 39 -- 48 distinct themes. Checked as a subset
    relationship (not equality) here, since the second batch has since
    added more; test_seeded_theme_count_reflects_the_second_coverage_expansion
    below is the current, up-to-date total-count guard.
    """
    entries = load_scripture_reference_definitions()
    themes = {entry["theme"] for entry in entries}
    assert _ORIGINAL_SEED_THEMES <= themes
    assert set(_FIRST_COVERAGE_EXPANSION_THEMES) <= themes


def test_seeded_theme_count_reflects_the_second_coverage_expansion():
    """The current, up-to-date total-theme-count guard: 9 original + 39
    (first batch) + 24 (second batch Tier 1) + 17 (second batch Tier 2)
    = 89 distinct covered themes, out of 107 total in
    theme_vocabulary.yaml -- and nothing beyond exactly this set (proves
    Tier 3 themes, and every other still-uncovered theme, stay out).
    """
    entries = load_scripture_reference_definitions()
    themes = {entry["theme"] for entry in entries}
    expected = (
        _ORIGINAL_SEED_THEMES
        | set(_FIRST_COVERAGE_EXPANSION_THEMES)
        | set(_SECOND_COVERAGE_EXPANSION_TIER1_THEMES)
        | set(_SECOND_COVERAGE_EXPANSION_TIER2_THEMES)
    )
    assert len(expected) == 89
    assert themes == expected


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
