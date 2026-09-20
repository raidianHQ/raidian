"""Builds the AI Narrative Layer's input (Step: AI Narrative Layer).
Trivial by design -- see DeterministicReadingContext's own docstring for
why this is not a reshaping/duplication of InterpretiveModel's fields.
"""

from __future__ import annotations

from app.schemas.ai_narrative import DeterministicReadingContext
from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.scripture_model import ScripturalPerspective


def build_deterministic_reading_context(
    model: InterpretiveModel, scripture: ScripturalPerspective | None
) -> DeterministicReadingContext:
    """`scripture` should be None whenever the caller did not explicitly
    opt in for this request -- see DeterministicReadingContext's own
    docstring for why this function never fetches Scripture itself.
    """
    return DeterministicReadingContext(interpretation=model, scripture=scripture)
