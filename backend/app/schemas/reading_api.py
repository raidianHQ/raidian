"""Request/response schemas for the Reading resource API (Step 24: Save
Reading / Reading History; Step 27: Reading creation). See
Documentation/SAVE_READING_DESIGN.md Section 5/7,
Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md Section 7/8,
Documentation/READING_CREATION_API_DESIGN.md Section 3/4.

Deliberately minimal: no Interpretation content, no NarrativeModel, no
unbounded history embedded per entry -- mirrors
app/schemas/interpretation_api.py::InterpretationHistoryEntry's own
"lightweight list entry" discipline, applied here to the Reading resource
itself. The exact same response shape (ReadingSummary) serves the Save
response, each Reading History list entry, and the creation response --
one schema, three call sites, no duplicated field set.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DrawMethod, ReadingStatus

_MAX_QUESTION_LENGTH = 4000
"""An implementation-safety default, not a Product Spec requirement --
Reading.question is an unbounded Text column with no governing document
specifying a limit. Comfortably exceeds any realistic reflection question
while guarding against a pathological payload. See
Documentation/READING_CREATION_API_DESIGN.md Section 4.
"""

_MAX_QUESTION_DOMAIN_LENGTH = 60
"""Matches Reading.question_domain's String(60) column exactly (not
arbitrary, unlike the question bound above) -- validating at this same
boundary here prevents a value that would silently succeed against SQLite
(dev/test, which does not enforce VARCHAR length) but fail as an unhandled
IntegrityError against PostgreSQL (production). See
Documentation/READING_CREATION_API_DESIGN.md Section 4.
"""


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields --
    the same discipline app/schemas/interpretation_api.py::_Model already
    applies, duplicated here (not imported) to keep this module
    independent, matching this project's existing per-resource schema
    module convention (interpretive_model.py, narrative_model.py each
    stand alone the same way).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class ReadingSummary(_Model):
    """The smallest useful representation of a Reading for API responses
    that don't need its full evidence/interpretation content -- derived
    directly from Reading's own columns (app/models/reading.py), no
    invented fields. Excludes spread_id/deck_id/draw_method: no current
    consumer (Save's confirmation response, or a History list entry) needs
    them, and no Reading Detail view exists yet to require them.
    """

    id: UUID
    status: ReadingStatus
    question: str
    question_domain: str | None
    created_at: datetime
    updated_at: datetime


class ReadingCreateRequest(_Model):
    """Request body for POST /readings. Deliberately has no owner/user
    field of any kind -- ownership always comes from Depends(get_current_user),
    never from client-supplied input
    (Documentation/READING_CREATION_API_DESIGN.md Section 3.1/12); `extra="forbid"`
    (inherited from _Model) additionally rejects any unrecognized field
    outright, including a client attempting to smuggle one in.
    """

    spread_id: UUID
    question: str = Field(max_length=_MAX_QUESTION_LENGTH)
    question_domain: str | None = Field(default=None, max_length=_MAX_QUESTION_DOMAIN_LENGTH)
    draw_method: DrawMethod = DrawMethod.PHYSICAL
    deck_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def _reject_blank_question(cls, value: str) -> str:
        """Mirrors Reading.validate_question()'s exact rule (blank or
        whitespace-only is invalid) but enforced here, at the request
        boundary, so that bare model-layer ValueError never has a chance
        to escape as an unhandled 500
        (Documentation/READING_CREATION_API_DESIGN.md Section 4/9).
        """
        if not value.strip():
            raise ValueError("question must not be blank")
        return value
