"""Tests for the compound-theme rule registry (INTERPRETATION_ENGINE_DESIGN.md
Section 9, Q4; RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 11).
"""

from app.models import Orientation
from app.services.interpretation.compounds import RULE_REGISTRY, match_compounds
from app.services.interpretation.context import build_reading_context
from tests.interpretation_helpers import build_reading


def test_registry_has_exactly_the_two_rules_supported_by_current_reference_data():
    ids = [rule.id for rule in RULE_REGISTRY]
    assert ids == ["clarity_vs_uncertainty", "intuition_within_uncertainty"]


def test_every_registered_rule_is_conditional_tier():
    assert all(rule.tier == "conditional" for rule in RULE_REGISTRY)


def test_clarity_vs_uncertainty_fires_when_both_tags_present(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),   # clarity
            ("Present Situation", "The Chariot", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),         # uncertainty
        ],
    )
    ctx = build_reading_context(reading)
    matches = match_compounds(ctx)

    fired = {m.rule_id for m in matches}
    assert "clarity_vs_uncertainty" in fired
    match = next(m for m in matches if m.rule_id == "clarity_vs_uncertainty")
    assert match.pattern_type == "tension"
    assert match.tension.pole_a == "clarity"
    assert match.tension.pole_b == "uncertainty"
    # citations point at the actual contributing draws
    cited_cards = {c.card_name for c in match.citations}
    assert cited_cards == {"Ace of Swords", "The Moon"}


def test_clarity_vs_uncertainty_does_not_fire_when_only_one_pole_present(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),  # clarity, no uncertainty anywhere
            ("Present Situation", "The Chariot", Orientation.UPRIGHT),
            ("Near Future", "The Sun", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    matches = match_compounds(ctx)

    assert "clarity_vs_uncertainty" not in {m.rule_id for m in matches}


def test_intuition_within_uncertainty_fires_when_both_tags_present(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "The High Priestess", Orientation.UPRIGHT),  # intuition
            ("Present Situation", "The Chariot", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),             # uncertainty
        ],
    )
    ctx = build_reading_context(reading)
    matches = match_compounds(ctx)

    fired = {m.rule_id for m in matches}
    assert "intuition_within_uncertainty" in fired
    match = next(m for m in matches if m.rule_id == "intuition_within_uncertainty")
    assert match.pattern_type == "theme"
    assert match.tension is None


def test_no_rules_fire_on_a_spread_with_none_of_the_relevant_themes(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Four of Wands", Orientation.UPRIGHT),
            ("Present Situation", "Ten of Pentacles", Orientation.UPRIGHT),
            ("Near Future", "Six of Pentacles", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    matches = match_compounds(ctx)
    assert matches == ()


def test_match_order_follows_registry_order_deterministically(seeded_session):
    """When both rules fire, the returned tuple's order must match
    RULE_REGISTRY's fixed order, not the order cards were drawn.
    """
    reading = build_reading(
        seeded_session, spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),      # clarity
            ("Challenge", "The Tower", Orientation.UPRIGHT),
            ("Foundation", "The Hermit", Orientation.UPRIGHT),
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Crown", "The Star", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),          # uncertainty
            ("Approach", "The Chariot", Orientation.UPRIGHT),
            ("External Influences", "The Empress", Orientation.UPRIGHT),
            ("Advice", "The High Priestess", Orientation.UPRIGHT),      # intuition
            ("Outcome", "Strength", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    matches = match_compounds(ctx)

    assert [m.rule_id for m in matches] == ["clarity_vs_uncertainty", "intuition_within_uncertainty"]


def test_match_compounds_is_deterministic_across_repeated_calls(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),
            ("Present Situation", "The Chariot", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    assert match_compounds(ctx) == match_compounds(ctx)
