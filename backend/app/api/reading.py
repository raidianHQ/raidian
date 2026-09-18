"""HTTP transport layer for the Reading resource: Reading creation, Save
Reading, and Reading History (Step 24; creation added Step 27). See
Documentation/READING_CREATION_API_DESIGN.md,
Documentation/SAVE_READING_DESIGN.md,
Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md,
Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md Section 10.

Thin routes only, mirroring app/api/interpretation.py's own discipline:
- POST /readings delegates entirely to
  app/services/reading_service.py::create_reading() -- ownership
  (Depends(get_current_user)), Spread/Deck existence, and the
  ReflectionSession+Reading construction all live there, not here.
- POST /readings/{reading_id}/save delegates the entire lifecycle
  transition to Reading.mark_saved() (app/models/reading.py) -- the sole
  authoritative domain operation, unchanged since Step 18. This route adds
  no lifecycle rule of its own.
- GET /readings queries Reading directly (there is no orchestration layer
  for a plain list-and-filter read, exactly as
  READING_HISTORY_OWNERSHIP_DESIGN.md Section 7 specifies) -- it never
  joins Interpretation, so cardinality is always exactly one row per
  Reading.

Ownership is enforced entirely by the existing, unmodified
app.api.dependencies dependencies -- get_current_user for creation and
History (there is no pre-existing reading_id to resolve for either), and
get_owned_reading for Save (a single, already-identified Reading). No new
ownership mechanism, no duplicated check, no client-suppliable owner field
anywhere in this module.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_reading
from app.db.session import get_db
from app.models.enums import ReadingStatus
from app.models.exceptions import DeckNotFoundError, ReadingNotSaveableError, SpreadNotFoundError
from app.models.reading import Reading
from app.models.reflection_session import ReflectionSession
from app.models.user import User
from app.schemas.reading_api import ReadingCreateRequest, ReadingSummary
from app.services.reading_service import create_reading

router = APIRouter(prefix="/readings", tags=["reading"])

_READING_NOT_SAVEABLE = "Reading cannot be saved from its current status"
_SPREAD_NOT_FOUND = "Spread not found"
_DECK_NOT_FOUND = "Deck not found"


def _to_summary(reading: Reading) -> ReadingSummary:
    return ReadingSummary(
        id=reading.id,
        status=reading.status,
        question=reading.question,
        question_domain=reading.question_domain,
        created_at=reading.created_at,
        updated_at=reading.updated_at,
    )


@router.post(
    "",
    response_model=ReadingSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Reading",
    description=(
        "Creates a new, owned Reading in DRAFTING status against an "
        "existing Spread (and, optionally, an existing Deck -- omitted "
        "resolves to the seeded default Deck). Ownership comes exclusively "
        "from the authenticated caller; the request body has no owner "
        "field. Creates no CardDraw, Interpretation, or Narrative rows. "
        "See Documentation/READING_CREATION_API_DESIGN.md Section 3."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": f"{_SPREAD_NOT_FOUND}, or {_DECK_NOT_FOUND.lower()}"},
        422: {"description": "Validation error"},
    },
)
def create_reading_route(
    body: ReadingCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReadingSummary:
    try:
        reading = create_reading(
            session,
            current_user,
            spread_id=body.spread_id,
            question=body.question,
            question_domain=body.question_domain,
            draw_method=body.draw_method,
            deck_id=body.deck_id,
        )
    except SpreadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_SPREAD_NOT_FOUND) from exc
    except DeckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_DECK_NOT_FOUND) from exc
    return _to_summary(reading)


@router.post(
    "/{reading_id}/save",
    response_model=ReadingSummary,
    summary="Save a Reading",
    description=(
        "Marks a Reading as SAVED -- the sole gate for its later "
        "appearance in Reading History. Allowed from SPREAD_COMPLETE or "
        "INTERPRETED; idempotent if already SAVED. Has no effect on "
        "Interpretation history, Narrative generation, or CardDraw data. "
        "See Documentation/SAVE_READING_DESIGN.md Section 5/6."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Reading not found"},
        409: {"description": _READING_NOT_SAVEABLE},
    },
)
def save_reading_route(reading: Reading = Depends(get_owned_reading)) -> ReadingSummary:
    try:
        reading.mark_saved()
    except ReadingNotSaveableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_summary(reading)


@router.get(
    "",
    response_model=list[ReadingSummary],
    summary="List the authenticated user's saved Readings",
    description=(
        "Reading History: every SAVED Reading owned by the authenticated "
        "caller, newest-first by updated_at. Never returns another "
        "user's Readings. No pagination; an empty history returns an "
        "empty list, not 404. See "
        "Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md Section 7/8."
    ),
    responses={401: {"description": "Not authenticated"}},
)
def list_saved_readings_route(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ReadingSummary]:
    readings = session.scalars(
        select(Reading)
        .join(ReflectionSession, Reading.reflection_session_id == ReflectionSession.id)
        .where(
            ReflectionSession.owner_id == current_user.id,
            Reading.status == ReadingStatus.SAVED,
        )
        .order_by(Reading.updated_at.desc())
    ).all()
    return [_to_summary(reading) for reading in readings]
