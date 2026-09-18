"""Validates the reference-data YAML content itself, independent of the
database -- these tests catch content problems (wrong counts, missing
fields, thin keyword lists) without needing to seed anything.
"""

import pytest

from app.seed.loader import (
    ReferenceDataError,
    load_all_spread_definitions,
    load_card_definitions,
    load_correspondence_definitions,
    load_theme_vocabulary,
    validate_card_definitions,
    validate_correspondence_definitions,
    validate_spread_definition,
)

MAJOR_ARCANA_NAMES = {
    "The Fool", "The Magician", "The High Priestess", "The Empress", "The Emperor",
    "The Hierophant", "The Lovers", "The Chariot", "Strength", "The Hermit",
    "Wheel of Fortune", "Justice", "The Hanged Man", "Death", "Temperance",
    "The Devil", "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World",
}


@pytest.fixture(scope="module")
def cards():
    return load_card_definitions()


@pytest.fixture(scope="module")
def spreads():
    return load_all_spread_definitions()


@pytest.fixture(scope="module")
def correspondences():
    return load_correspondence_definitions()


def test_exactly_78_cards(cards):
    assert len(cards) == 78


def test_22_major_arcana(cards):
    majors = [c for c in cards if c["arcana"] == "major"]
    assert len(majors) == 22
    assert {c["name"] for c in majors} == MAJOR_ARCANA_NAMES


def test_56_minor_arcana(cards):
    minors = [c for c in cards if c["arcana"] == "minor"]
    assert len(minors) == 56


def test_four_suits_of_fourteen(cards):
    minors = [c for c in cards if c["arcana"] == "minor"]
    counts: dict[str, int] = {}
    for card in minors:
        counts[card["suit"]] = counts.get(card["suit"], 0) + 1
    assert counts == {"wands": 14, "cups": 14, "swords": 14, "pentacles": 14}


def test_rank_structure_is_complete_and_unique(cards):
    major_ranks = sorted((int(c["rank"]) for c in cards if c["arcana"] == "major"))
    assert major_ranks == list(range(22))

    expected_minor_ranks = {
        "ace", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "page", "knight", "queen", "king",
    }
    for suit in ("wands", "cups", "swords", "pentacles"):
        ranks = {c["rank"] for c in cards if c["arcana"] == "minor" and c["suit"] == suit}
        assert ranks == expected_minor_ranks


def test_major_arcana_have_no_suit(cards):
    assert all(c.get("suit") is None for c in cards if c["arcana"] == "major")


def test_minor_arcana_have_a_suit(cards):
    assert all(c.get("suit") in {"wands", "cups", "swords", "pentacles"} for c in cards if c["arcana"] == "minor")


def test_card_names_are_unique(cards):
    names = [c["name"] for c in cards]
    assert len(names) == len(set(names))


def test_all_required_content_fields_are_populated(cards):
    required_text_fields = (
        "name", "rank", "image_ref", "base_meaning_upright", "base_meaning_reversed",
    )
    required_list_fields = ("keywords", "primary_themes", "secondary_themes")

    for card in cards:
        for field in required_text_fields:
            assert card.get(field) and card[field].strip(), f"{card.get('name')}: missing {field}"
        for field in required_list_fields:
            assert card.get(field), f"{card.get('name')}: missing {field}"


def test_keywords_are_not_reduced_to_single_generic_words(cards):
    for card in cards:
        assert len(card["keywords"]) >= 4, f"{card['name']}: too few keywords ({len(card['keywords'])})"


def test_real_content_passes_validation(cards):
    validate_card_definitions(cards)  # must not raise


def test_validation_catches_wrong_card_count():
    with pytest.raises(ReferenceDataError):
        validate_card_definitions([])


def test_validation_catches_duplicate_name(cards):
    broken = list(cards)
    duplicate = dict(broken[0])
    duplicate["name"] = broken[1]["name"]
    broken[0] = duplicate

    with pytest.raises(ReferenceDataError) as exc_info:
        validate_card_definitions(broken)
    assert any("duplicate card names" in problem for problem in exc_info.value.problems)


def test_validation_catches_major_arcana_with_a_suit(cards):
    broken = [dict(c) for c in cards]
    for card in broken:
        if card["arcana"] == "major":
            card["suit"] = "wands"
            break

    with pytest.raises(ReferenceDataError) as exc_info:
        validate_card_definitions(broken)
    assert any("must not have a suit" in problem for problem in exc_info.value.problems)


def test_validation_catches_thin_keywords(cards):
    broken = [dict(c) for c in cards]
    broken[0] = dict(broken[0], keywords=["only", "two"])

    with pytest.raises(ReferenceDataError) as exc_info:
        validate_card_definitions(broken)
    assert any("keywords" in problem for problem in exc_info.value.problems)


# --- Spreads -----------------------------------------------------------


def test_expected_spreads_exist(spreads):
    assert {s["name"] for s in spreads} == {"Single Card", "Three Card", "Celtic Cross"}


def test_all_spread_definitions_pass_validation(spreads):
    for spread in spreads:
        validate_spread_definition(spread)  # must not raise


def test_celtic_cross_covers_the_required_semantic_roles(spreads):
    celtic_cross = next(s for s in spreads if s["name"] == "Celtic Cross")
    roles = {position["semantic_role"] for position in celtic_cross["positions"]}

    required_roles = {
        "situation", "recent_past", "influence_blocker",
        "near_future", "advice", "advice_clarifier",
    }
    assert required_roles.issubset(roles)


def test_three_card_spread_has_three_positions(spreads):
    three_card = next(s for s in spreads if s["name"] == "Three Card")
    assert len(three_card["positions"]) == 3


def test_single_card_spread_has_one_position(spreads):
    single_card = next(s for s in spreads if s["name"] == "Single Card")
    assert len(single_card["positions"]) == 1


def test_validation_catches_non_contiguous_position_order():
    broken = {
        "name": "Broken Spread",
        "positions": [
            {"name": "A", "position_order": 1, "semantic_role": "general", "required": True},
            {"name": "B", "position_order": 3, "semantic_role": "general", "required": True},
        ],
    }
    with pytest.raises(ReferenceDataError) as exc_info:
        validate_spread_definition(broken)
    assert any("contiguous" in problem for problem in exc_info.value.problems)


# --- Correspondence data -------------------------------------------------
# See Documentation/RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md for the
# source spreadsheet, the corrections applied, and the approved decisions
# these tests encode.


def test_exactly_78_correspondence_entries(correspondences):
    assert len(correspondences) == 78


def test_every_card_has_exactly_one_correspondence_entry(cards, correspondences):
    card_names = {c["name"] for c in cards}
    corr_names = [c["name"] for c in correspondences]

    assert set(corr_names) == card_names
    assert len(corr_names) == len(set(corr_names))


def test_real_correspondence_content_passes_validation(cards, correspondences):
    validate_correspondence_definitions(cards, correspondences)  # must not raise


def test_correspondences_record_their_source(correspondences):
    for entry in correspondences:
        assert entry["source_reference"], f"{entry.get('name')}: missing source_reference"


def test_minor_arcana_are_labeled_golden_dawn_tradition(cards, correspondences):
    minor_names = {c["name"] for c in cards if c["arcana"] == "minor"}
    for entry in correspondences:
        if entry["name"] in minor_names:
            assert entry["tradition_name"] == "Golden Dawn decanic attribution"


def test_major_arcana_tradition_left_null_where_not_confidently_identified(cards, correspondences):
    major_names = {c["name"] for c in cards if c["arcana"] == "major"}
    for entry in correspondences:
        if entry["name"] in major_names:
            assert entry["tradition_name"] is None


def test_strength_correspondence_corrected_to_leo(correspondences):
    entry = next(c for c in correspondences if c["name"] == "Strength")
    assert entry["zodiac_signs"] == ["leo"]


def test_judgement_correspondence_corrected_to_scorpio(correspondences):
    entry = next(c for c in correspondences if c["name"] == "Judgement")
    assert entry["zodiac_signs"] == ["scorpio"]


def test_astrology_notes_are_original_not_copied_source_prose(correspondences):
    """Guards against ever pasting the source spreadsheet's long narrative
    paragraphs back in. The source's shortest non-empty Astrology paragraph
    is 166 characters and its longest run well past 1000; our notes --
    including the richer two-sentence notes from the enrichment pass
    (RAIDIAN_WISE_THEME_VOCABULARY_V1.md) -- top out around 380. 450 stays
    a comfortable ceiling above our own content while still catching an
    accidental full-paragraph paste.
    """
    for entry in correspondences:
        note = entry.get("astrology_note")
        if note:
            assert len(note) < 450, f"{entry['name']}: astrology_note looks too long to be a brief original note"


def test_validation_catches_correspondence_for_unknown_card(cards):
    broken = [{
        "name": "Not A Real Card",
        "source_reference": "test",
        "tradition_name": None,
        "element": "fire",
        "zodiac_signs": ["aries"],
        "zodiac_symbols": ["♈"],
        "astrological_influence": "Mars",
        "elemental_gender": None,
        "direction": "south",
        "color": "red",
        "animal": None,
        "stone": None,
        "astrology_note": None,
    }]
    with pytest.raises(ReferenceDataError) as exc_info:
        validate_correspondence_definitions(cards, broken)
    assert any("no card named" in problem for problem in exc_info.value.problems)


def test_validation_catches_missing_correspondence_for_a_card(cards, correspondences):
    incomplete = [c for c in correspondences if c["name"] != "The Fool"]
    with pytest.raises(ReferenceDataError) as exc_info:
        validate_correspondence_definitions(cards, incomplete)
    assert any("no correspondence entry" in problem for problem in exc_info.value.problems)


def test_validation_catches_mismatched_symbol_and_sign_counts(cards, correspondences):
    broken = [dict(c) for c in correspondences]
    broken[0] = dict(broken[0], zodiac_signs=["aries", "leo"], zodiac_symbols=["♈"])

    with pytest.raises(ReferenceDataError) as exc_info:
        validate_correspondence_definitions(cards, broken)
    assert any("length" in problem for problem in exc_info.value.problems)


# --- Theme vocabulary normalization ---------------------------------------
# See Documentation/RAIDIAN_WISE_THEME_VOCABULARY_V1.md for the full merge
# mapping and rationale this section verifies against.

REMOVED_THEME_TAGS = {
    "surrender", "painful_ending", "perseverance", "moderation",
    "disruption", "connection", "change", "swift_action",
    # NOTE: `healing` -> `recovery` was proposed and reverted on review;
    # `healing` remains a canonical tag (RAIDIAN_WISE_THEME_VOCABULARY_V1.md,
    # Section 4) and must NOT be in this removed-tags set.
}


@pytest.fixture(scope="module")
def theme_vocabulary():
    return load_theme_vocabulary()


def test_theme_vocabulary_has_no_duplicates(theme_vocabulary):
    # load_theme_vocabulary() itself returns a set, so this also exercises
    # that the underlying YAML list had no duplicate entries to begin with.
    raw = load_theme_vocabulary()
    assert len(raw) == len(theme_vocabulary)


def test_theme_vocabulary_is_107_canonical_tags(theme_vocabulary):
    assert len(theme_vocabulary) == 107


def test_healing_remains_a_canonical_tag(theme_vocabulary):
    """healing -> recovery was proposed and reverted on review (Section 4,
    RAIDIAN_WISE_THEME_VOCABULARY_V1.md): the two name distinct processes
    (restoration/renewal vs. regaining strength after difficulty).
    """
    assert "healing" in theme_vocabulary


def test_all_78_cards_present_after_normalization(cards):
    assert len(cards) == 78


def test_all_cards_still_have_populated_themes_after_normalization(cards):
    for card in cards:
        assert card["primary_themes"], f"{card['name']}: primary_themes is empty"
        assert card["secondary_themes"], f"{card['name']}: secondary_themes is empty"


def test_every_used_theme_tag_is_in_the_canonical_vocabulary(cards, theme_vocabulary):
    used = set()
    for c in cards:
        used.update(c["primary_themes"])
        used.update(c["secondary_themes"])
    assert used.issubset(theme_vocabulary)


def test_removed_tags_no_longer_appear_anywhere(cards):
    used = set()
    for c in cards:
        used.update(c["primary_themes"])
        used.update(c["secondary_themes"])
    assert used.isdisjoint(REMOVED_THEME_TAGS)


def test_no_card_lost_theme_richness_from_merging(cards):
    """The three cards whose two primary themes merged into one tag were
    each given a second, accurate replacement (Section 3.1 of the
    vocabulary doc) -- none should have been left at a single primary
    theme as a side effect of deduplication.
    """
    by_name = {c["name"]: c for c in cards}
    for name in ("The Hanged Man", "Ten of Swords", "Nine of Wands"):
        assert len(by_name[name]["primary_themes"]) == 2, name


def test_the_star_retains_healing(cards):
    """healing -> recovery was reverted specifically for The Star; it must
    carry its original `healing` tag, not `recovery`.
    """
    star = next(c for c in cards if c["name"] == "The Star")
    assert "healing" in star["primary_themes"]
    assert "recovery" not in star["primary_themes"]


def test_no_card_has_overlapping_primary_and_secondary_themes(cards):
    for c in cards:
        overlap = set(c["primary_themes"]) & set(c["secondary_themes"])
        assert not overlap, f"{c['name']}: {overlap}"


def test_validation_catches_a_tag_outside_the_vocabulary(cards):
    broken = [dict(c) for c in cards]
    broken[0] = dict(broken[0], primary_themes=["not_a_real_canonical_tag"])

    with pytest.raises(ReferenceDataError) as exc_info:
        validate_card_definitions(broken)
    assert any("not in the canonical theme vocabulary" in p for p in exc_info.value.problems)


def test_real_card_content_passes_vocabulary_validation(cards):
    validate_card_definitions(cards)  # must not raise


# --- Astrology note enrichment (the 20 formerly-formulaic notes) ---------

FORMULAIC_CARDS = [
    "Ace of Wands", "King of Wands", "Queen of Wands", "Knight of Wands", "Page of Wands",
    "Ace of Cups", "King of Cups", "Queen of Cups", "Knight of Cups", "Page of Cups",
    "Ace of Swords", "King of Swords", "Queen of Swords", "Knight of Swords", "Page of Swords",
    "Ace of Pentacles", "King of Pentacles", "Queen of Pentacles", "Knight of Pentacles", "Page of Pentacles",
]

OLD_FORMULAIC_PREFIX = "In the Golden Dawn tradition, this card is associated with"


def test_exactly_20_cards_were_previously_formulaic():
    assert len(FORMULAIC_CARDS) == 20


def test_all_20_formerly_formulaic_notes_were_rewritten(correspondences):
    by_name = {c["name"]: c for c in correspondences}
    for name in FORMULAIC_CARDS:
        note = by_name[name]["astrology_note"]
        assert not note.startswith(OLD_FORMULAIC_PREFIX), f"{name}: still has the old formulaic note"


def test_revised_notes_explain_qualities_not_just_repeat_the_raw_value(correspondences):
    """The revised notes must do more than restate astrological_influence
    verbatim -- they should be substantively longer, reflecting the added
    explanation of qualities and how they may color the card.
    """
    by_name = {c["name"]: c for c in correspondences}
    for name in FORMULAIC_CARDS:
        entry = by_name[name]
        note = entry["astrology_note"]
        assert len(note) > len(entry["astrological_influence"]) + 100, (
            f"{name}: revised note doesn't look substantively richer than the raw influence value"
        )


def test_revised_notes_use_reflective_non_predictive_language(correspondences):
    by_name = {c["name"]: c for c in correspondences}
    for name in FORMULAIC_CARDS:
        note = by_name[name]["astrology_note"]
        assert "may be expressed" in note, f"{name}: missing the reflective 'may be expressed' framing"
