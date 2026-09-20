"""Reads and validates the YAML reference-data source files under
app/reference_data/ -- the human-reviewable content that app.seed.seed
loads into the database.

This module never touches the database. It only knows how to parse YAML
into plain dicts and check that they satisfy the constraints the schema
(and the Interpretation Engine that will eventually consume this content)
depends on. Keeping parsing/validation separate from persistence means the
content can be validated (and tested) without a database at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.enums import Arcana, SemanticRole, Suit

REFERENCE_DATA_DIR = Path(__file__).resolve().parents[1] / "reference_data"
RWS_DECK_DIR = REFERENCE_DATA_DIR / "rider_waite_smith"
SPREADS_DIR = REFERENCE_DATA_DIR / "spreads"
THEME_VOCABULARY_PATH = REFERENCE_DATA_DIR / "theme_vocabulary.yaml"
SCRIPTURE_REFERENCES_PATH = REFERENCE_DATA_DIR / "scripture_references.yaml"

_MAJOR_RANKS = {str(n) for n in range(22)}
_MINOR_RANKS = {"ace", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "page", "knight", "queen", "king"}
_SUITS = {member.value for member in Suit}
_MIN_KEYWORDS = 4

_ZODIAC_SIGNS = {
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
}
_ELEMENTS = {"fire", "water", "air", "earth"}
_DIRECTIONS = {"north", "south", "east", "west"}
_ELEMENTAL_GENDERS = {"masculine", "feminine"}

# The 66 canonical Protestant-canon Bible book names, exactly as they must
# appear in scripture_references.yaml's own `book` field -- prevents a
# typo or an invented/non-canonical book name from ever being seeded.
BIBLE_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
    "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
}

# Only translations already confirmed public-domain (no license needed for
# quotation) are approved for MVP -- Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md
# Section 15.1/16 Q5, still open for any other translation. This governs
# the `translation` *label* only; no translation's passage text is stored
# or shown by this project today regardless of this list.
APPROVED_SCRIPTURE_TRANSLATIONS = {"KJV", "WEB", "ASV"}

# Card-meaning files within a deck directory. Explicit allowlist rather than
# "every *.yaml except deck.yaml" -- deck.yaml, and non-meaning files like
# correspondences.yaml, must not be swept up as card entries.
_CARD_MEANING_FILES = ("major_arcana.yaml", "wands.yaml", "cups.yaml", "swords.yaml", "pentacles.yaml")


class ReferenceDataError(ValueError):
    """Raised when a reference-data source file fails validation.

    Carries every problem found (not just the first), so a content review
    pass can fix everything in one go rather than one error at a time.
    """

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Reference data validation failed:\n- " + "\n- ".join(problems))


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- Theme vocabulary --------------------------------------------------
#
# A single, closed, deck-agnostic controlled vocabulary that every card's
# primary_themes/secondary_themes must draw from -- see
# Documentation/RAIDIAN_WISE_THEME_VOCABULARY_V1.md for the consolidation
# that produced it. Enforced here so a future content edit can't silently
# reintroduce a near-duplicate tag or a typo.


def load_theme_vocabulary(path: Path = THEME_VOCABULARY_PATH) -> set[str]:
    tags = _load_yaml(path)
    if not isinstance(tags, list):
        raise ReferenceDataError([f"{path}: expected a YAML list of theme tags"])
    return set(tags)


# --- Deck + Cards -----------------------------------------------------------


def load_deck_definition(deck_dir: Path = RWS_DECK_DIR) -> dict:
    return _load_yaml(deck_dir / "deck.yaml")


def load_card_definitions(deck_dir: Path = RWS_DECK_DIR) -> list[dict]:
    """Concatenates the deck's card-meaning files (_CARD_MEANING_FILES), in a
    stable, deterministic order. Explicitly excludes deck.yaml and
    correspondences.yaml, which are not card-meaning content.
    """
    card_files = sorted(deck_dir / name for name in _CARD_MEANING_FILES if (deck_dir / name).exists())
    cards: list[dict] = []
    for path in card_files:
        entries = _load_yaml(path)
        if not isinstance(entries, list):
            raise ReferenceDataError([f"{path}: expected a YAML list of card entries"])
        cards.extend(entries)
    return cards


def validate_card_definitions(cards: list[dict], theme_vocabulary: set[str] | None = None) -> None:
    """`theme_vocabulary` defaults to the real controlled vocabulary
    (THEME_VOCABULARY_PATH); tests pass a synthetic set to validate that
    check in isolation without depending on the real content file.
    """
    if theme_vocabulary is None:
        theme_vocabulary = load_theme_vocabulary()

    problems: list[str] = []

    if len(cards) != 78:
        problems.append(f"expected 78 cards, found {len(cards)}")

    names_seen: dict[str, int] = {}
    major_count = 0
    minor_suit_counts: dict[str, int] = {suit: 0 for suit in _SUITS}
    major_ranks_seen: set[str] = set()
    minor_ranks_seen: dict[str, set[str]] = {suit: set() for suit in _SUITS}

    required_text_fields = ("name", "rank", "image_ref", "base_meaning_upright", "base_meaning_reversed")
    required_list_fields = ("keywords", "primary_themes", "secondary_themes")

    for i, card in enumerate(cards):
        label = card.get("name", f"<entry {i}>")

        for field in required_text_fields:
            value = card.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{label}: field '{field}' must be a non-empty string")

        for field in required_list_fields:
            value = card.get(field)
            if not isinstance(value, list) or not value:
                problems.append(f"{label}: field '{field}' must be a non-empty list")

        keywords = card.get("keywords")
        if isinstance(keywords, list) and len(keywords) < _MIN_KEYWORDS:
            problems.append(
                f"{label}: expected at least {_MIN_KEYWORDS} keywords, found {len(keywords)} "
                "(single generic keywords are not sufficient content)"
            )

        for field in ("primary_themes", "secondary_themes"):
            tags = card.get(field)
            if isinstance(tags, list):
                unknown = [t for t in tags if t not in theme_vocabulary]
                if unknown:
                    problems.append(
                        f"{label}: {field} contains tag(s) not in the canonical theme "
                        f"vocabulary: {unknown} (see theme_vocabulary.yaml)"
                    )

        name = card.get("name")
        if isinstance(name, str):
            names_seen[name] = names_seen.get(name, 0) + 1

        arcana = card.get("arcana")
        suit = card.get("suit")
        rank = card.get("rank")

        if arcana == Arcana.MAJOR.value:
            major_count += 1
            if suit is not None:
                problems.append(f"{label}: Major Arcana card must not have a suit (found {suit!r})")
            if isinstance(rank, str):
                if rank in major_ranks_seen:
                    problems.append(f"{label}: duplicate Major Arcana rank {rank!r}")
                major_ranks_seen.add(rank)
        elif arcana == Arcana.MINOR.value:
            if suit not in _SUITS:
                problems.append(f"{label}: Minor Arcana card must have a valid suit, found {suit!r}")
            else:
                minor_suit_counts[suit] += 1
                if isinstance(rank, str):
                    if rank in minor_ranks_seen[suit]:
                        problems.append(f"{label}: duplicate rank {rank!r} within suit {suit!r}")
                    minor_ranks_seen[suit].add(rank)
        else:
            problems.append(f"{label}: field 'arcana' must be 'major' or 'minor', found {arcana!r}")

    duplicate_names = [name for name, count in names_seen.items() if count > 1]
    if duplicate_names:
        problems.append(f"duplicate card names within the deck: {sorted(duplicate_names)}")

    if major_count != 22:
        problems.append(f"expected 22 Major Arcana cards, found {major_count}")
    if major_ranks_seen and major_ranks_seen != _MAJOR_RANKS:
        missing = _MAJOR_RANKS - major_ranks_seen
        extra = major_ranks_seen - _MAJOR_RANKS
        if missing:
            problems.append(f"Major Arcana missing ranks: {sorted(missing, key=int)}")
        if extra:
            problems.append(f"Major Arcana has unexpected ranks: {sorted(extra)}")

    for suit in sorted(_SUITS):
        count = minor_suit_counts[suit]
        if count != 14:
            problems.append(f"expected 14 cards for suit {suit!r}, found {count}")
        ranks = minor_ranks_seen[suit]
        if ranks and ranks != _MINOR_RANKS:
            missing = _MINOR_RANKS - ranks
            extra = ranks - _MINOR_RANKS
            if missing:
                problems.append(f"suit {suit!r} missing ranks: {sorted(missing)}")
            if extra:
                problems.append(f"suit {suit!r} has unexpected ranks: {sorted(extra)}")

    if problems:
        raise ReferenceDataError(problems)


# --- Card Correspondences ------------------------------------------------
#
# A distinct, separately-sourced layer from the card meanings above -- see
# Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md (Section 8) and
# RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md for sourcing.


def load_correspondence_definitions(deck_dir: Path = RWS_DECK_DIR) -> list[dict]:
    path = deck_dir / "correspondences.yaml"
    entries = _load_yaml(path)
    if not isinstance(entries, list):
        raise ReferenceDataError([f"{path}: expected a YAML list of correspondence entries"])
    return entries


def validate_correspondence_definitions(cards: list[dict], correspondences: list[dict]) -> None:
    """Validates correspondence entries both internally and against the
    card set they annotate -- every card must have exactly one
    correspondence entry, and vice versa.
    """
    problems: list[str] = []

    card_names = {c["name"] for c in cards if isinstance(c.get("name"), str)}
    corr_names_seen: dict[str, int] = {}

    required_text_fields = ("source_reference", "element", "astrological_influence", "direction", "color")

    for entry in correspondences:
        label = entry.get("name", "<unnamed correspondence entry>")

        for field in required_text_fields:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{label}: field '{field}' must be a non-empty string")

        name = entry.get("name")
        if isinstance(name, str):
            corr_names_seen[name] = corr_names_seen.get(name, 0) + 1
            if name not in card_names:
                problems.append(f"{label}: no card named {name!r} exists in the card definitions")

        element = entry.get("element")
        if isinstance(element, str) and element not in _ELEMENTS:
            problems.append(f"{label}: element {element!r} is not one of {sorted(_ELEMENTS)}")

        direction = entry.get("direction")
        if isinstance(direction, str) and direction not in _DIRECTIONS:
            problems.append(f"{label}: direction {direction!r} is not one of {sorted(_DIRECTIONS)}")

        gender = entry.get("elemental_gender")
        if gender is not None and gender not in _ELEMENTAL_GENDERS:
            problems.append(f"{label}: elemental_gender {gender!r} is not one of {sorted(_ELEMENTAL_GENDERS)} (or null)")

        signs = entry.get("zodiac_signs")
        if not isinstance(signs, list) or not signs:
            problems.append(f"{label}: 'zodiac_signs' must be a non-empty list")
        else:
            bad_signs = [s for s in signs if s not in _ZODIAC_SIGNS]
            if bad_signs:
                problems.append(f"{label}: unrecognized zodiac sign(s) {bad_signs}")

        symbols = entry.get("zodiac_symbols")
        if not isinstance(symbols, list) or not symbols:
            problems.append(f"{label}: 'zodiac_symbols' must be a non-empty list")
        elif isinstance(signs, list) and len(symbols) != len(signs):
            problems.append(
                f"{label}: 'zodiac_symbols' length ({len(symbols)}) must match 'zodiac_signs' length ({len(signs)})"
            )

    duplicate_names = [name for name, count in corr_names_seen.items() if count > 1]
    if duplicate_names:
        problems.append(f"duplicate correspondence entries for card(s): {sorted(duplicate_names)}")

    missing_cards = card_names - set(corr_names_seen)
    if missing_cards:
        problems.append(f"cards with no correspondence entry: {sorted(missing_cards)}")

    if problems:
        raise ReferenceDataError(problems)


# --- Scripture References -------------------------------------------------
#
# A deliberately separate, optional content layer -- see
# Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15. Keyed by theme,
# never by card; reuses theme_vocabulary.yaml's own closed vocabulary
# rather than maintaining an independent taxonomy.


def load_scripture_reference_definitions(path: Path = SCRIPTURE_REFERENCES_PATH) -> list[dict]:
    entries = _load_yaml(path)
    if not isinstance(entries, list):
        raise ReferenceDataError([f"{path}: expected a YAML list of scripture reference entries"])
    return entries


def validate_scripture_reference_definitions(
    entries: list[dict], theme_vocabulary: set[str] | None = None
) -> None:
    """`theme_vocabulary` defaults to the real controlled vocabulary
    (THEME_VOCABULARY_PATH), mirroring validate_card_definitions()'s own
    parameter -- tests pass a synthetic set to validate this check in
    isolation.
    """
    if theme_vocabulary is None:
        theme_vocabulary = load_theme_vocabulary()

    problems: list[str] = []
    required_text_fields = (
        "theme", "book", "reference_display", "translation", "context_note", "reflection_connection",
    )
    seen_keys: dict[tuple, int] = {}

    for i, entry in enumerate(entries):
        label = entry.get("reference_display") or entry.get("theme") or f"<entry {i}>"

        for field in required_text_fields:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{label}: field '{field}' must be a non-empty string")

        theme = entry.get("theme")
        if isinstance(theme, str) and theme not in theme_vocabulary:
            problems.append(
                f"{label}: theme {theme!r} is not in the canonical theme vocabulary "
                "(see theme_vocabulary.yaml) -- Scripture themes must reuse an existing "
                "tag, never invent a new one"
            )

        book = entry.get("book")
        if isinstance(book, str) and book not in BIBLE_BOOKS:
            problems.append(f"{label}: book {book!r} is not a recognized Bible book name")

        translation = entry.get("translation")
        if isinstance(translation, str) and translation not in APPROVED_SCRIPTURE_TRANSLATIONS:
            problems.append(
                f"{label}: translation {translation!r} is not an approved, public-domain "
                f"translation ({sorted(APPROVED_SCRIPTURE_TRANSLATIONS)}) -- "
                "Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15.1"
            )

        chapter = entry.get("chapter")
        if not isinstance(chapter, int) or isinstance(chapter, bool) or chapter < 1:
            problems.append(f"{label}: 'chapter' must be a positive integer")

        verse_start = entry.get("verse_start")
        if not isinstance(verse_start, int) or isinstance(verse_start, bool) or verse_start < 1:
            problems.append(f"{label}: 'verse_start' must be a positive integer")

        verse_end = entry.get("verse_end")
        if verse_end is not None:
            valid_verse_end = isinstance(verse_end, int) and not isinstance(verse_end, bool)
            if not valid_verse_end or (isinstance(verse_start, int) and verse_end < verse_start):
                problems.append(f"{label}: 'verse_end' must be null or an integer >= verse_start")

        if (
            isinstance(theme, str) and isinstance(book, str) and isinstance(chapter, int)
            and isinstance(verse_start, int) and isinstance(translation, str)
        ):
            key = (theme, book, chapter, verse_start, translation)
            seen_keys[key] = seen_keys.get(key, 0) + 1

    duplicates = [key for key, count in seen_keys.items() if count > 1]
    if duplicates:
        problems.append(f"duplicate scripture reference entries (theme, book, chapter, verse_start, translation): {duplicates}")

    if problems:
        raise ReferenceDataError(problems)


# --- Spreads ------------------------------------------------------------


def load_spread_definition(path: Path) -> dict:
    return _load_yaml(path)


def load_all_spread_definitions(spreads_dir: Path = SPREADS_DIR) -> list[dict]:
    return [load_spread_definition(p) for p in sorted(spreads_dir.glob("*.yaml"))]


def validate_spread_definition(spread: dict) -> None:
    problems: list[str] = []
    label = spread.get("name", "<unnamed spread>")

    if not isinstance(spread.get("name"), str) or not spread["name"].strip():
        problems.append(f"{label}: 'name' must be a non-empty string")

    positions = spread.get("positions")
    if not isinstance(positions, list) or not positions:
        problems.append(f"{label}: 'positions' must be a non-empty list")
        raise ReferenceDataError(problems)

    valid_roles = {member.value for member in SemanticRole}
    orders_seen: set[int] = set()

    for position in positions:
        pos_label = f"{label} / {position.get('name', '<unnamed position>')}"

        if not isinstance(position.get("name"), str) or not position["name"].strip():
            problems.append(f"{pos_label}: 'name' must be a non-empty string")

        order = position.get("position_order")
        if not isinstance(order, int) or order < 1:
            problems.append(f"{pos_label}: 'position_order' must be a positive integer")
        elif order in orders_seen:
            problems.append(f"{pos_label}: duplicate position_order {order}")
        else:
            orders_seen.add(order)

        role = position.get("semantic_role")
        if role not in valid_roles:
            problems.append(f"{pos_label}: 'semantic_role' {role!r} is not a recognized SemanticRole")

        if not isinstance(position.get("required"), bool):
            problems.append(f"{pos_label}: 'required' must be a boolean")

    expected_orders = set(range(1, len(positions) + 1))
    if orders_seen and orders_seen != expected_orders:
        problems.append(
            f"{label}: position_order values {sorted(orders_seen)} are not a contiguous "
            f"1..{len(positions)} sequence"
        )

    if problems:
        raise ReferenceDataError(problems)
