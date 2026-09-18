"""Persists an already-computed InterpretiveModel. Deliberately separate
from engine.interpret() (which is pure) -- see
Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 8: this mirrors the
loader/seed split already used for reference data (parse+validate vs.
write), applied here to compute vs. persist.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ReadingStatus
from app.models.interpretation import Interpretation
from app.models.reading import Reading
from app.schemas.interpretive_model import InterpretiveModel


def _next_sequence(session: Session) -> int:
    """One past the current global maximum `Interpretation.sequence`, or 1
    if no Interpretation rows exist yet -- see Interpretation.sequence's
    own docstring for why this is a global counter, not scoped per
    reading, and why it is unique-constrained rather than
    concurrency-locked.
    """
    current_max = session.execute(select(func.max(Interpretation.sequence))).scalar()
    return (current_max or 0) + 1


def save_interpretation(
    session: Session, reading: Reading, model: InterpretiveModel
) -> Interpretation:
    """Creates a new Interpretation row for `reading`.

    Never modifies CardDraw or any other evidence row
    (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 17) -- and never modifies or
    removes a prior Interpretation row, so reinterpreting preserves
    history (INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1).

    Status transition is transition-aware, not unconditional
    (Documentation/READING_INTEGRATION_DESIGN.md Section 5, Resolved Q1):
    DRAFTING/SPREAD_COMPLETE -> INTERPRETED (first-time advancement),
    INTERPRETED -> INTERPRETED (idempotent no-op), but SAVED is left
    untouched -- reinterpreting a saved Reading must never silently
    regress its lifecycle status backward.

    Does not commit -- the caller controls the transaction boundary
    (Documentation/READING_INTEGRATION_DESIGN.md Section 14), exactly as
    every existing caller of this function already does.
    """
    interpretation = Interpretation(
        reading=reading,
        engine_version=model.engine_version,
        reference_data_version=model.reference_data_version,
        interpretive_model=model.model_dump(mode="json"),
        sequence=_next_sequence(session),
    )
    session.add(interpretation)
    if reading.status != ReadingStatus.SAVED:
        reading.status = ReadingStatus.INTERPRETED
    session.flush()
    return interpretation
