"""HTTP transport layer for the AI Narrative Layer (ADR-0005's Reflection
Engine, RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 12).

Thin routes only -- mirrors app/api/interpretation.py and
app/api/scripture.py's own discipline exactly: ownership resolved via
get_owned_reading, all actual work delegated to
app/services/reading_orchestration.py, no AI prompt construction, provider
call, or response parsing happens here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_reading, get_reflection_engine_client
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.ai_narrative import AINarrative
from app.models.reading import Reading
from app.schemas.ai_narrative import AINarrativeResponse, AINarrativeSummary
from app.services.ai_narrative.generation import AINarrativeProviderError, AINarrativeValidationError
from app.services.reading_orchestration import (
    generate_ai_narrative_for_reading,
    get_current_ai_narrative_for_reading,
)
from app.services.reflection_engine.client import ReflectionEngineClient, ReflectionEngineNotConfiguredError

router = APIRouter(prefix="/readings/{reading_id}", tags=["ai-narrative"])

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"
_NEVER_INTERPRETED = "Reading has never been interpreted"
_NOT_CONFIGURED = "The AI Narrative Layer is not configured"
_GENERATION_FAILED = "AI Narrative generation failed"


def _to_summary(ai_narrative: AINarrative) -> AINarrativeSummary:
    return AINarrativeSummary(
        id=ai_narrative.id,
        interpretation_id=ai_narrative.interpretation_id,
        sequence=ai_narrative.sequence,
        created_at=ai_narrative.created_at,
        ai_narrative=AINarrativeResponse.model_validate(ai_narrative.ai_narrative),
    )


@router.post(
    "/ai-narrative",
    response_model=AINarrativeSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an AI Narrative for a Reading",
    description=(
        "Runs the AI Narrative Layer (via the Reflection Engine, ADR-0005) "
        "against the Reading's current InterpretiveModel and persists a new "
        "AINarrative row. Not idempotent -- every call generates and stores "
        "a new attempt, mirroring POST /interpret. `include_scripture` opts "
        "this one call in to also weaving in the reading's current "
        "ScripturalPerspective; omit it (or pass false) for a purely tarot "
        "narrative. A failed generation never touches the deterministic "
        "Interpretation -- the reading remains fully usable either way."
    ),
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or {_NEVER_INTERPRETED.lower()}"},
        502: {"description": _GENERATION_FAILED},
        503: {"description": _NOT_CONFIGURED},
    },
)
def generate_ai_narrative_route(
    include_scripture: bool = Query(default=False),
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
    client: ReflectionEngineClient = Depends(get_reflection_engine_client),
    settings: Settings = Depends(get_settings),
) -> AINarrativeSummary:
    try:
        ai_narrative = generate_ai_narrative_for_reading(
            session,
            reading,
            client,
            include_scripture=include_scripture,
            provider="anthropic",
            model=settings.ai_model,
        )
    except AINarrativeProviderError as exc:
        if isinstance(exc.__cause__, ReflectionEngineNotConfiguredError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=_GENERATION_FAILED) from exc
    except AINarrativeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=_GENERATION_FAILED) from exc

    if ai_narrative is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NEVER_INTERPRETED)
    return _to_summary(ai_narrative)


@router.get(
    "/ai-narrative/current",
    response_model=AINarrativeSummary,
    summary="Retrieve the current AI Narrative",
    description=(
        "Returns the highest-sequence AINarrative generated against this "
        "Reading's current Interpretation. Never regenerates -- call POST "
        "/ai-narrative first."
    ),
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": f"{_READING_NOT_FOUND}, or no AI narrative has been generated yet"},
    },
)
def get_current_ai_narrative_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> AINarrativeSummary:
    ai_narrative = get_current_ai_narrative_for_reading(session, reading)
    if ai_narrative is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No AI narrative has been generated for this reading's current interpretation",
        )
    return _to_summary(ai_narrative)
