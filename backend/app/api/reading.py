"""HTTP transport layer for the Reading resource: Reading creation, Save
Reading, Reading History (Step 24; creation added Step 27), CardDraw
recording (Step 32), and Reading retrieval (Step 43). See
Documentation/READING_CREATION_API_DESIGN.md,
Documentation/SAVE_READING_DESIGN.md,
Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md,
Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md Section 10,
Documentation/CARDDRAW_API_DESIGN.md,
Documentation/READING_DETAIL_API_DESIGN.md.

Thin routes only, mirroring app/api/interpretation.py's own discipline:
- POST /readings delegates entirely to
  app/services/reading_service.py::create_reading() -- ownership
  (Depends(get_current_user)), Spread/Deck existence, and the
  ReflectionSession+Reading construction all live there, not here.
- GET /readings/{reading_id} queries Reading directly (there is no
  orchestration layer for a plain detail read, the same discipline the
  History route below already established) -- it deliberately excludes
  interpretation/narrative content, which remain the responsibility of
  the four existing interpretation/narrative routes
  (app/api/interpretation.py), unchanged and untouched by this route.
- POST /readings/{reading_id}/draws delegates entirely to
  app/services/reading_service.py::record_card_draw() -- position/card
  existence, the already-filled-position check, draw_order computation,
  and the actual lifecycle mutation (via Reading.add_card_draw()) all
  live there, not here.
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
get_owned_reading for Save, CardDraw recording, and Reading retrieval
(each acts against a single, already-identified Reading). No new
ownership mechanism, no duplicated check, no client-suppliable owner
field anywhere in this module.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, get_owned_reading
from app.api.reference_data import _to_card_summary, _to_spread_summary
from app.db.session import get_db
from app.models.card_draw import CardDraw
from app.models.enums import ReadingStatus
from app.models.exceptions import (
    CardNotFoundError,
    DeckNotFoundError,
    DuplicateCardError,
    PositionAlreadyDrawnError,
    ReadingNotDraftingError,
    ReadingNotSaveableError,
    SpreadNotFoundError,
    SpreadPositionNotFoundError,
)
from app.models.reading import Reading
from app.models.reflection_session import ReflectionSession
from app.models.spread import Spread
from app.models.user import User
from app.schemas.reading_api import (
    CardDrawCreateRequest,
    CardDrawSummary,
    ReadingCardDrawSummary,
    ReadingCreateRequest,
    ReadingDetail,
    ReadingSummary,
)
from app.schemas.reference_data_api import SpreadPositionSummary
from app.services.reading_service import create_reading, record_card_draw

router = APIRouter(prefix="/readings", tags=["reading"])

_READING_NOT_SAVEABLE = "Reading cannot be saved from its current status"
_SPREAD_NOT_FOUND = "Spread not found"
_DECK_NOT_FOUND = "Deck not found"
_POSITION_NOT_FOUND = "Spread position not found"
_CARD_NOT_FOUND = "Card not found"
_POSITION_ALREADY_DRAWN = "Position has already been drawn in this reading"
_DUPLICATE_CARD = "Card has already been drawn in this reading"
_READING_NOT_DRAFTING = "Reading cannot accept card draws from its current status"


def _to_summary(reading: Reading) -> ReadingSummary:
    return ReadingSummary(
        id=reading.id,
        status=reading.status,
        question=reading.question,
        question_domain=reading.question_domain,
        created_at=reading.created_at,
        updated_at=reading.updated_at,
    )


def _to_draw_summary(draw: CardDraw, reading: Reading) -> CardDrawSummary:
    return CardDrawSummary(
        id=draw.id,
        position_id=draw.position_id,
        card_id=draw.card_id,
        orientation=draw.orientation,
        draw_order=draw.draw_order,
        created_at=draw.created_at,
        reading_status=reading.status,
    )


def _to_reading_card_draw_summary(draw: CardDraw) -> ReadingCardDrawSummary:
    position = draw.position
    return ReadingCardDrawSummary(
        id=draw.id,
        position=SpreadPositionSummary(
            id=position.id,
            name=position.name,
            description=position.description,
            position_order=position.position_order,
            semantic_role=position.semantic_role,
            required=position.required,
        ),
        card=_to_card_summary(draw.card),
        orientation=draw.orientation,
        draw_order=draw.draw_order,
        created_at=draw.created_at,
    )


def _to_detail(reading: Reading) -> ReadingDetail:
    return ReadingDetail(
        id=reading.id,
        status=reading.status,
        question=reading.question,
        question_domain=reading.question_domain,
        draw_method=reading.draw_method,
        created_at=reading.created_at,
        updated_at=reading.updated_at,
        spread_id=reading.spread_id,
        spread=_to_spread_summary(reading.spread),
        deck_id=reading.deck_id,
        card_draws=[_to_reading_card_draw_summary(draw) for draw in reading.card_draws],
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


@router.get(
    "/{reading_id}",
    response_model=ReadingDetail,
    summary="Retrieve a Reading's full current state",
    description=(
        "Full Reading evidence state -- Spread (with positions) and "
        "every CardDraw (with its Card and SpreadPosition) -- for "
        "Reading Detail / Spread Review. Does not include interpretation "
        "or narrative content; see POST /readings/{reading_id}/interpret, "
        "GET .../interpretations(/current), and GET .../narrative for "
        "those, unchanged. See Documentation/READING_DETAIL_API_DESIGN.md."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Reading not found"},
    },
)
def get_reading_detail_route(
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
) -> ReadingDetail:
    detailed = session.scalars(
        select(Reading)
        .where(Reading.id == reading.id)
        .options(
            selectinload(Reading.spread).selectinload(Spread.positions),
            selectinload(Reading.card_draws).selectinload(CardDraw.position),
            selectinload(Reading.card_draws).selectinload(CardDraw.card),
        )
    ).one()
    return _to_detail(detailed)


@router.post(
    "/{reading_id}/draws",
    response_model=CardDrawSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Record a CardDraw for a Reading",
    description=(
        "Records a single card drawn into one position of an owned, "
        "DRAFTING Reading. draw_order is computed server-side and is "
        "never accepted from the client. If this draw fills the last "
        "required SpreadPosition, the Reading automatically advances to "
        "SPREAD_COMPLETE -- reflected in this response's reading_status "
        "field. See Documentation/CARDDRAW_API_DESIGN.md Section 3/4."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": f"Reading not found, {_POSITION_NOT_FOUND.lower()}, or {_CARD_NOT_FOUND.lower()}"},
        409: {
            "description": f"{_READING_NOT_DRAFTING}, {_DUPLICATE_CARD.lower()}, "
            f"or {_POSITION_ALREADY_DRAWN.lower()}"
        },
        422: {"description": "Validation error"},
    },
)
def record_card_draw_route(
    body: CardDrawCreateRequest,
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
) -> CardDrawSummary:
    try:
        draw = record_card_draw(
            session,
            reading,
            position_id=body.position_id,
            card_id=body.card_id,
            orientation=body.orientation,
        )
    except SpreadPositionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_POSITION_NOT_FOUND) from exc
    except CardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_CARD_NOT_FOUND) from exc
    except PositionAlreadyDrawnError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_POSITION_ALREADY_DRAWN) from exc
    except DuplicateCardError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_CARD) from exc
    except ReadingNotDraftingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_READING_NOT_DRAFTING) from exc
    return _to_draw_summary(draw, reading)


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
