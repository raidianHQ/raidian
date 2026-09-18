"""Tests for context.build_reading_context -- especially that structural
ordering follows SpreadPosition.position_order, not CardDraw.draw_order
(INTERPRETATION_ENGINE_DESIGN.md Section 2.2).
"""

from app.models import Orientation
from app.services.interpretation.context import build_reading_context
from tests.interpretation_helpers import build_reading


def test_context_orders_draws_by_position_order_not_draw_order(seeded_session):
    """Celtic Cross's Recent Past position (position_order 4) sits
    structurally after its Situation position (order 1) -- but here we
    physically/data-entry draw Recent Past FIRST (draw_order 1) and
    Situation SECOND (draw_order 2). The context must still order by
    position_order, i.e. Situation before Recent Past.
    """
    reading = build_reading(
        seeded_session,
        spread_name="Celtic Cross",
        draws=[
            ("Recent Past", "The Fool", Orientation.UPRIGHT),   # draw_order 1, position_order 4
            ("Situation", "The Sun", Orientation.UPRIGHT),       # draw_order 2, position_order 1
        ],
    )

    ctx = build_reading_context(reading)

    assert [d.position_name for d in ctx.draws] == ["Situation", "Recent Past"]
    assert [d.position_order for d in ctx.draws] == [1, 4]


def test_context_resolves_upright_meaning_text(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Fool", Orientation.UPRIGHT)],
    )
    ctx = build_reading_context(reading)
    assert ctx.draws[0].meaning_text == reading.card_draws[0].card.base_meaning_upright
    assert ctx.draws[0].meaning_text != reading.card_draws[0].card.base_meaning_reversed


def test_context_resolves_reversed_meaning_text(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Fool", Orientation.REVERSED)],
    )
    ctx = build_reading_context(reading)
    assert ctx.draws[0].meaning_text == reading.card_draws[0].card.base_meaning_reversed


def test_all_themes_preserves_primary_then_secondary_order_and_dedupes(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Fool", Orientation.UPRIGHT)],
    )
    ctx = build_reading_context(reading)
    draw = ctx.draws[0]

    assert draw.all_themes[: len(draw.primary_themes)] == draw.primary_themes
    assert len(draw.all_themes) == len(set(draw.all_themes))  # deduped


def test_draws_with_role_filters_correctly(seeded_session):
    from app.models.enums import SemanticRole

    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Present Situation", "The Sun", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)

    situation_draws = ctx.draws_with_role(SemanticRole.SITUATION)
    assert len(situation_draws) == 1
    assert situation_draws[0].card_name == "The Sun"

    advice_draws = ctx.draws_with_role(SemanticRole.ADVICE)
    assert advice_draws == ()


def test_context_carries_question_and_domain(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Fool", Orientation.UPRIGHT)],
        question="Will this project succeed?",
        question_domain="career",
    )
    ctx = build_reading_context(reading)
    assert ctx.question == "Will this project succeed?"
    assert ctx.question_domain == "career"
