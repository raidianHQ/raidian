"""Unit tests for app/services/ai_narrative/persistence.py -- mirrors the
(unfile-scoped) coverage interpretation/persistence.py already gets via
the orchestration/API test suites, applied one layer over.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import AINarrative, Orientation
from app.schemas.ai_narrative import AINarrativeResponse
from app.services.ai_narrative.persistence import save_ai_narrative
from app.services.interpretation.engine import interpret
from app.services.interpretation.persistence import save_interpretation
from tests.interpretation_helpers import build_reading


def _response(**overrides) -> AINarrativeResponse:
    defaults: dict = dict(
        schema_version="1.0", source_schema_version="1.0", generated_at=datetime.now(timezone.utc),
        provider="anthropic", model="claude-test",
        opening_summary="An opening.", overall_narrative="A narrative.",
        key_themes=("clarity",), card_relationships=(), reflective_synthesis="A synthesis.",
        reflection_questions=("What feels most true here?",), scriptural_reflection=None,
    )
    defaults.update(overrides)
    return AINarrativeResponse(**defaults)


def _interpretation(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
    )
    model = interpret(reading, seeded_session)
    return save_interpretation(seeded_session, reading, model)


def test_save_ai_narrative_creates_a_row_tied_to_the_interpretation(seeded_session):
    interpretation = _interpretation(seeded_session)
    response = _response()

    row = save_ai_narrative(seeded_session, interpretation, response)

    assert row.interpretation_id == interpretation.id
    assert row.provider == "anthropic"
    assert row.model == "claude-test"
    assert row.ai_narrative["opening_summary"] == "An opening."


def test_save_ai_narrative_assigns_increasing_sequence_and_keeps_history(seeded_session):
    interpretation = _interpretation(seeded_session)

    first = save_ai_narrative(seeded_session, interpretation, _response(opening_summary="First attempt."))
    second = save_ai_narrative(seeded_session, interpretation, _response(opening_summary="Second attempt."))

    assert second.sequence > first.sequence
    rows = seeded_session.execute(
        select(AINarrative).where(AINarrative.interpretation_id == interpretation.id)
    ).scalars().all()
    assert len(rows) == 2
    assert {row.ai_narrative["opening_summary"] for row in rows} == {"First attempt.", "Second attempt."}


def test_save_ai_narrative_round_trips_the_response_through_json(seeded_session):
    interpretation = _interpretation(seeded_session)
    response = _response(
        key_themes=("clarity", "patience"), card_relationships=("A and B reinforce one another.",),
        scriptural_reflection="A short reflection.",
    )

    row = save_ai_narrative(seeded_session, interpretation, response)
    seeded_session.flush()
    seeded_session.expire(row)

    reloaded = AINarrativeResponse.model_validate(row.ai_narrative)
    assert reloaded == response
