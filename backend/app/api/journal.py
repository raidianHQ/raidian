"""HTTP transport layer for Journal entries. Thin routes only, mirroring
app/api/scripture.py's own discipline -- ownership via get_owned_reading,
all persistence delegated to app/services/journal_service.py.

Nested under /readings/{reading_id}, like every other Reading-scoped
resource in this API (interpretation, narrative, scripture, ai-narrative)
-- not the flat top-level `/journals` docs/NAMING_CONVENTIONS.md's route
sketch names, the same deliberate deviation
SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md already made for Scripture, for
the same reason: consistency with every route actually implemented in this
project outweighs a pre-implementation naming sketch.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_reading
from app.db.session import get_db
from app.models.journal_entry import JournalEntry
from app.models.reading import Reading
from app.schemas.journal import JournalEntryCreateRequest, JournalEntrySummary
from app.services.journal_service import create_journal_entry, list_journal_entries

router = APIRouter(prefix="/readings/{reading_id}", tags=["journal"])

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"


def _to_summary(entry: JournalEntry) -> JournalEntrySummary:
    return JournalEntrySummary(
        id=entry.id,
        reading_id=entry.reading_id,
        sequence=entry.sequence,
        content=entry.content,
        created_at=entry.created_at,
    )


@router.post(
    "/journal-entries",
    response_model=JournalEntrySummary,
    status_code=status.HTTP_201_CREATED,
    summary="Write a Journal entry for a Reading",
    description=(
        "Records one private, user-written reflection against this "
        "Reading. Independent of interpretation/AI/Scripture -- always "
        "available, even if the reading has never been interpreted."
    ),
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": _READING_NOT_FOUND},
        422: {"description": "Validation error"},
    },
)
def create_journal_entry_route(
    body: JournalEntryCreateRequest,
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
) -> JournalEntrySummary:
    entry = create_journal_entry(session, reading, content=body.content)
    return _to_summary(entry)


@router.get(
    "/journal-entries",
    response_model=list[JournalEntrySummary],
    summary="List a Reading's Journal entries",
    description="Every Journal entry written against this Reading, oldest-first. An empty list, not 404, if none exist yet.",
    responses={
        401: {"description": _NOT_AUTHENTICATED},
        404: {"description": _READING_NOT_FOUND},
    },
)
def list_journal_entries_route(
    reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db)
) -> list[JournalEntrySummary]:
    return [_to_summary(entry) for entry in list_journal_entries(session, reading)]
