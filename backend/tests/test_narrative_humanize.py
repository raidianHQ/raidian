"""Tests for the mechanical snake_case -> Title Case transform
(NARRATIVE_LAYER_DESIGN.md Section 7). No database needed -- pure string
function.
"""

from app.services.narrative.humanize import humanize_tag


def test_humanizes_a_simple_two_word_tag():
    assert humanize_tag("new_beginnings") == "New Beginnings"


def test_humanizes_a_single_word_tag():
    assert humanize_tag("clarity") == "Clarity"


def test_lowercases_minor_words_except_when_first():
    assert humanize_tag("skill_and_craft") == "Skill and Craft"


def test_keeps_minor_word_capitalized_when_it_is_the_first_word():
    # No tag in the real vocabulary starts with a minor word, but the rule
    # itself (index > 0) must not accidentally lowercase a leading one.
    assert humanize_tag("the_fool_theme") == "The Fool Theme"


def test_every_theme_vocabulary_tag_humanizes_without_error():
    """Runs the transform over the real, current 107-tag vocabulary to
    confirm it is safe (no crash, no empty output, no leading/trailing
    whitespace) against every tag that actually exists today -- not just
    hand-picked examples. load_theme_vocabulary() is a pure YAML parser
    (no database involved), consistent with this being a no-DB test file.
    """
    from app.seed.loader import load_theme_vocabulary

    tags = load_theme_vocabulary()
    for tag in tags:
        result = humanize_tag(tag)
        assert result, f"empty humanization for {tag!r}"
        assert result == result.strip(), f"whitespace issue humanizing {tag!r} -> {result!r}"
        assert "_" not in result, f"underscore survived humanizing {tag!r} -> {result!r}"


def test_is_idempotent_on_an_already_humanized_card_name():
    """Card.name values (e.g. "The Fool", "Ace of Swords") are never
    supposed to be passed through this function (design doc Section 7),
    but it must not corrupt them if it happens to receive one -- e.g. a
    card-name fallback value (engine.py's _derive_role_explained falls
    back to draw.card_name when a draw has no primary_themes).
    """
    assert humanize_tag("The Fool") == "The Fool"
    assert humanize_tag("Ace of Swords") == "Ace of Swords"


def test_is_deterministic():
    assert humanize_tag("self_evaluation") == humanize_tag("self_evaluation")
