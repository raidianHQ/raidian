"""HTTP transport layer for Reading interpretation/narrative (Step 11).

Thin routes only. Every route resolves `reading_id` -> `Reading` (the only
direct query this module performs) and then delegates entirely to
app/services/reading_orchestration.py -- the API never queries
Interpretation directly, never constructs InterpretiveModel/NarrativeModel
by hand, and implements no interpretation or narrative rule of its own.
See Documentation/INTERPRETATION_API_DESIGN.md Section 2/16.

No authentication or authorization exists anywhere in this codebase yet
(INTERPRETATION_API_DESIGN.md Sections 4-5) -- every route below is fully
unauthenticated and performs no ownership check. This is an explicitly
flagged interim state (acceptable only pre-launch, with no real user
data), not an oversight, and not something this module invents a stopgap
for; see that document for the missing infrastructure this depends on.

Write-transaction handling (commit on success / rollback on exception) is
the responsibility of the `get_db` dependency
(app/db/session.py, INTERPRETATION_API_DESIGN.md Section 14), not this
module -- routes here only ever flush (via the orchestration layer they
call), exactly as that layer's own docstring requires.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.interpretation import Interpretation
from app.models.reading import Reading
from app.schemas.interpretation_api import InterpretationHistoryEntry, InterpretationSummary
from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.narrative_model import NarrativeModel
from app.services.reading_orchestration import (
    ReadingNotReadyForInterpretationError,
    get_current_interpretation,
    get_narrative_for_reading,
    interpret_reading,
    list_interpretations,
)

router = APIRouter(prefix="/readings/{reading_id}", tags=["interpretation"])

_READING_NOT_FOUND = "Reading not found"
_NEVER_INTERPRETED = "Reading has never been interpreted"


def _get_reading_or_404(session: Session, reading_id: UUID) -> Reading:
    reading = session.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_READING_NOT_FOUND)
    return reading


def _to_summary(interpretation: Interpretation) -> InterpretationSummary:
    """Deserializes an already-engine-produced, already-persisted JSON blob
    via InterpretiveModel.model_validate -- the same proven-safe operation
    reading_orchestration.get_narrative_for_reading() already performs, not
    "manual construction" in the boundary's prohibited sense
    (INTERPRETATION_API_DESIGN.md Section 3.2).
    """
    return InterpretationSummary(
        id=interpretation.id,
        reading_id=interpretation.reading_id,
        sequence=interpretation.sequence,
        engine_version=interpretation.engine_version,
        reference_data_version=interpretation.reference_data_version,
        created_at=interpretation.created_at,
        interpretive_model=InterpretiveModel.model_validate(interpretation.interpretive_model),
    )


def _to_history_entry(interpretation: Interpretation) -> InterpretationHistoryEntry:
    return InterpretationHistoryEntry(
        id=interpretation.id,
        sequence=interpretation.sequence,
        engine_version=interpretation.engine_version,
        reference_data_version=interpretation.reference_data_version,
        created_at=interpretation.created_at,
    )


@router.post(
    "/interpret",
    response_model=InterpretationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger interpretation for a Reading",
    description=(
        "Runs the deterministic Interpretation Engine against a "
        "spread-complete Reading and persists a new Interpretation row, "
        "preserving reinterpretation history. Not idempotent -- every call "
        "creates a new row. See "
        "Documentation/INTERPRETATION_API_DESIGN.md Section 2, 7, 13."
    ),
    responses={
        404: {"description": _READING_NOT_FOUND},
        409: {"description": "Reading is not spread-complete"},
    },
)
def interpret_reading_route(reading_id: UUID, session: Session = Depends(get_db)) -> InterpretationSummary:
    reading = _get_reading_or_404(session, reading_id)
    try:
        interpretation = interpret_reading(session, reading)
    except ReadingNotReadyForInterpretationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_summary(interpretation)


@router.get(
    "/interpretations/current",
    response_model=InterpretationSummary,
    summary="Retrieve the current interpretation",
    description=(
        "Returns the highest-sequence Interpretation for this Reading, "
        "including its full InterpretiveModel. See "
        "Documentation/INTERPRETATION_API_DESIGN.md Section 2, 7."
    ),
    responses={404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"}},
)
def get_current_interpretation_route(
    reading_id: UUID, session: Session = Depends(get_db)
) -> InterpretationSummary:
    reading = _get_reading_or_404(session, reading_id)
    interpretation = get_current_interpretation(session, reading)
    if interpretation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NEVER_INTERPRETED)
    return _to_summary(interpretation)


@router.get(
    "/interpretations",
    response_model=list[InterpretationHistoryEntry],
    summary="Retrieve interpretation history",
    description=(
        "Returns every Interpretation for this Reading, newest-first. "
        "Lightweight entries only -- omits the full InterpretiveModel. "
        "No pagination. See Documentation/INTERPRETATION_API_DESIGN.md "
        "Section 2, 12."
    ),
    responses={404: {"description": _READING_NOT_FOUND}},
)
def list_interpretations_route(
    reading_id: UUID, session: Session = Depends(get_db)
) -> list[InterpretationHistoryEntry]:
    reading = _get_reading_or_404(session, reading_id)
    return [_to_history_entry(interpretation) for interpretation in list_interpretations(session, reading)]


@router.get(
    "/narrative",
    response_model=NarrativeModel,
    summary="Retrieve the current narrative",
    description=(
        "Assembles the NarrativeModel on demand from the current "
        "persisted Interpretation. Never persisted or cached -- "
        "recomputed on every call. See "
        "Documentation/INTERPRETATION_API_DESIGN.md Section 2, 9."
    ),
    responses={404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"}},
)
def get_narrative_route(reading_id: UUID, session: Session = Depends(get_db)) -> NarrativeModel:
    reading = _get_reading_or_404(session, reading_id)
    narrative = get_narrative_for_reading(session, reading)
    if narrative is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NEVER_INTERPRETED)
    return narrative
