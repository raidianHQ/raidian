"""HTTP transport layer for the optional Scriptural Reflection layer
(Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15).

A dedicated router, separate from app/api/interpretation.py -- mirrors
this project's own architectural separation between tarot interpretation
and Scripture (interpretive_model.py vs. scripture_model.py,
app/services/interpretation/ vs. app/services/scripture/) all the way up
to the API surface, rather than folding one more route into
interpretation.py's own router the way /narrative was.

Thin route only: resolves `reading_id` -> an owned `Reading` via
app.api.dependencies.get_owned_reading (authentication + ownership,
identical to every other Reading-scoped route in this project) and
delegates entirely to app/services/reading_orchestration.py -- this
module never queries Interpretation or ScriptureReference directly and
implements no Scripture-selection rule of its own.

Scripture is OPTIONAL by construction here: this route is a separate,
opt-in fetch a caller makes only if it wants a Scriptural Reflection --
GET /readings/{reading_id}/interpretations/current and
GET /readings/{reading_id}/narrative are entirely unaffected by whether
this route is ever called. See app/services/reading_orchestration.py's
own module docstring for why this still counts as "optional" without a
stored per-Reading/per-User flag at this foundation stage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_reading
from app.db.session import get_db
from app.models.reading import Reading
from app.schemas.scripture_model import ScripturalPerspective
from app.services.reading_orchestration import (
    get_current_scriptural_reflection_for_reading,
    get_scripture_for_reading,
)

router = APIRouter(prefix="/readings/{reading_id}", tags=["scripture"])

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"
_NEVER_INTERPRETED = "Reading has never been interpreted"
_NO_SNAPSHOT_YET = "No Scriptural Reflection has been generated for this reading's current interpretation"


@router.get(
    "/scripture",
    response_model=ScripturalPerspective,
    summary="Retrieve the optional Scriptural Reflection for a Reading",
    description=(
        "Deterministically maps the current interpretation's own "
        "established themes to an approved Scripture reference dataset "
        "-- never an LLM, never a per-card mapping. The first call for a "
        "given interpretation selects and, if it finds at least one "
        "approved reference, persists a ScripturalReflection snapshot; "
        "every later call for that same interpretation returns the "
        "persisted snapshot as-is, without re-querying the (mutable) "
        "Scripture reference dataset -- so a saved/reopened reading's "
        "Scriptural Reflection cannot silently change later. An empty "
        "result (no approved reference for any of this reading's themes) "
        "is never persisted, so a later addition to the approved dataset "
        "can still be found on this reading's next request. See "
        "Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15."
    ),
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"},
    },
)
def get_scripture_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> ScripturalPerspective:
    perspective = get_scripture_for_reading(session, reading)
    if perspective is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NEVER_INTERPRETED)
    return perspective


@router.get(
    "/scripture/current",
    response_model=ScripturalPerspective,
    summary="Retrieve the previously persisted Scriptural Reflection, without selecting one",
    description=(
        "Returns the persisted ScripturalReflection snapshot for this "
        "reading's current interpretation, if GET /scripture has already "
        "been called for it at least once and found an approved match. "
        "Never selects, computes, or persists anything itself -- a free, "
        "read-only check, mirroring GET /ai-narrative/current. A 404 "
        "here is the ordinary, expected outcome for a reading whose "
        "Scriptural Reflection has never been shown (or was shown but "
        "found no approved match) -- never surfaced as an error the "
        "caller caused."
    ),
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or {_NO_SNAPSHOT_YET.lower()}"},
    },
)
def get_current_scriptural_reflection_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> ScripturalPerspective:
    perspective = get_current_scriptural_reflection_for_reading(session, reading)
    if perspective is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_SNAPSHOT_YET)
    return perspective
