"""HTTP transport layer for Reading interpretation/narrative (Step 11,
retrofitted for authentication/ownership in Step 22).

Thin routes only. Every route resolves `reading_id` -> an owned `Reading`
via app.api.dependencies.get_owned_reading (authentication + ownership,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 6)
and then delegates entirely to app/services/reading_orchestration.py -- the
API never queries Interpretation directly, never constructs
InterpretiveModel/NarrativeModel by hand, and implements no interpretation
or narrative rule of its own. See
Documentation/INTERPRETATION_API_DESIGN.md Section 2/16.

Authentication/ownership enforcement happens entirely inside
get_owned_reading, before any route body below ever runs -- orchestration,
the Interpretation Engine, and the Narrative Layer remain fully
ownership-agnostic (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
Section 9), unchanged by this retrofit.

Write-transaction handling (commit on success / rollback on exception) is
the responsibility of the `get_db` dependency
(app/db/session.py, INTERPRETATION_API_DESIGN.md Section 14), not this
module -- routes here only ever flush (via the orchestration layer they
call), exactly as that layer's own docstring requires.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_reading
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

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"
_NEVER_INTERPRETED = "Reading has never been interpreted"


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
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": _READING_NOT_FOUND},
        409: {"description": "Reading is not spread-complete"},
    },
)
def interpret_reading_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> InterpretationSummary:
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
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"},
    },
)
def get_current_interpretation_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> InterpretationSummary:
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
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": _READING_NOT_FOUND},
    },
)
def list_interpretations_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> list[InterpretationHistoryEntry]:
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
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"},
    },
)
def get_narrative_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> NarrativeModel:
    narrative = get_narrative_for_reading(session, reading)
    if narrative is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NEVER_INTERPRETED)
    return narrative
