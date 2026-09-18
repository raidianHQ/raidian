"""The Reading Integration orchestration layer (Step 9).

The only module permitted to combine database access with calls into the
deterministic Interpretation Engine (app/services/interpretation/) and the
deterministic, database-free Narrative Layer (app/services/narrative/) --
mirrors the loader/seed and compute/persist separations already
established elsewhere in this project. See
Documentation/READING_INTEGRATION_DESIGN.md Section 13.

Neither function here commits or rolls back the session -- the caller
controls the transaction boundary
(Documentation/READING_INTEGRATION_DESIGN.md Section 14), exactly as
interpretation/persistence.py's own save_interpretation already does.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interpretation import Interpretation
from app.models.reading import Reading
from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.narrative_model import NarrativeModel
from app.services.interpretation.engine import interpret
from app.services.interpretation.persistence import save_interpretation
from app.services.narrative.assembler import assemble_narrative


class ReadingNotReadyForInterpretationError(ValueError):
    """Raised by interpret_reading() when `reading.is_spread_complete` is
    False -- checked BEFORE engine.interpret() is invoked at all
    (Documentation/READING_INTEGRATION_DESIGN.md Section 3). Stronger than
    engine.interpret()'s own precondition (which only rejects a Reading
    with zero CardDraws); that check remains in place as defense-in-depth,
    not as the primary guard.
    """


def interpret_reading(session: Session, reading: Reading) -> Interpretation:
    """Runs the full Reading -> Interpretation Engine -> persistence
    sequence for `reading`
    (Documentation/READING_INTEGRATION_DESIGN.md Sections 2-5).

    Triggerable regardless of `reading.status`'s current value (DRAFTING,
    SPREAD_COMPLETE, INTERPRETED, or SAVED are all accepted) -- the only
    precondition is evidence-based: every required SpreadPosition on
    `reading.spread` must have a drawn card. Raises
    ReadingNotReadyForInterpretationError if not, before any engine or
    persistence call is made -- no Interpretation row is created and
    `reading.status` is left untouched.

    A new Interpretation row is always created on success, never reusing
    or overwriting a prior one (Section 6) -- calling this function again
    later against the same Reading is the entire reinterpretation
    mechanism; no special-case logic exists here for it. No duplicate-run
    detection or skipping is performed (Section 11, Resolved Q3 --
    deliberately deferred, not implemented).

    Does not commit or roll back -- see module docstring.
    """
    if not reading.is_spread_complete:
        raise ReadingNotReadyForInterpretationError(
            f"reading {reading.id} is not spread-complete: not every required "
            "position on its spread has a drawn card"
        )

    model: InterpretiveModel = interpret(reading, session)
    return save_interpretation(session, reading, model)


def get_narrative_for_reading(session: Session, reading: Reading) -> NarrativeModel | None:
    """Assembles the narrative for `reading`'s current interpretation --
    the Interpretation row with the highest `sequence` for this
    `reading_id` (Documentation/READING_INTEGRATION_DESIGN.md Section 7,
    Resolved Q2) -- or None if `reading` has never been interpreted.

    Performs the only database read anywhere in the narrative path: fetches
    the current Interpretation row and reconstructs its InterpretiveModel
    via `InterpretiveModel.model_validate(...)` (an already-proven-lossless
    round-trip -- test_save_interpretation_round_trips_the_model_through_json),
    then hands that already-materialized object to the pure, database-free
    `assemble_narrative()` (NARRATIVE_LAYER_DESIGN.md Section 2/4).

    NarrativeModel is never persisted or cached here (Section 9, Resolved
    Q4) -- every call recomputes it from the persisted Interpretation. If
    narrative assembly itself raises, nothing about the already-persisted
    Interpretation row is touched or affected -- this function performs no
    write of any kind (Section 10/12).
    """
    latest = session.execute(
        select(Interpretation)
        .where(Interpretation.reading_id == reading.id)
        .order_by(Interpretation.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is None:
        return None

    model = InterpretiveModel.model_validate(latest.interpretive_model)
    return assemble_narrative(model)
