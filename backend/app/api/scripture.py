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
from app.services.reading_orchestration import get_scripture_for_reading

router = APIRouter(prefix="/readings/{reading_id}", tags=["scripture"])

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"
_NEVER_INTERPRETED = "Reading has never been interpreted"


@router.get(
    "/scripture",
    response_model=ScripturalPerspective,
    summary="Retrieve the optional Scriptural Reflection for a Reading",
    description=(
        "Deterministically maps the current interpretation's own "
        "established themes to an approved Scripture reference dataset "
        "-- never an LLM, never a per-card mapping. Never persisted or "
        "cached -- recomputed on every call. `reflections` may "
        "legitimately be empty if none of this reading's themes have an "
        "approved mapping yet. See "
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
