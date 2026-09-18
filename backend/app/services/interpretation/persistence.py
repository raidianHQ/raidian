"""Persists an already-computed InterpretiveModel. Deliberately separate
from engine.interpret() (which is pure) -- see
Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 8: this mirrors the
loader/seed split already used for reference data (parse+validate vs.
write), applied here to compute vs. persist.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.enums import ReadingStatus
from app.models.interpretation import Interpretation
from app.models.reading import Reading
from app.schemas.interpretive_model import InterpretiveModel


def save_interpretation(
    session: Session, reading: Reading, model: InterpretiveModel
) -> Interpretation:
    """Creates a new Interpretation row for `reading` and transitions the
    Reading to INTERPRETED. Never modifies CardDraw or any other evidence
    row (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 17) -- and never modifies
    or removes a prior Interpretation row, so reinterpreting preserves
    history (INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1).
    """
    interpretation = Interpretation(
        reading=reading,
        engine_version=model.engine_version,
        reference_data_version=model.reference_data_version,
        interpretive_model=model.model_dump(mode="json"),
    )
    session.add(interpretation)
    reading.status = ReadingStatus.INTERPRETED
    session.flush()
    return interpretation
