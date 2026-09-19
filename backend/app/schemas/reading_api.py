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

from app.models.enums import DrawMethod, Orientation, ReadingStatus
from app.schemas.reference_data_api import CardSummary, SpreadPositionSummary, SpreadSummary

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


class CardDrawCreateRequest(_Model):
    """Request body for POST /readings/{reading_id}/draws (Step 32,
    Documentation/CARDDRAW_API_DESIGN.md Section 4.1).

    Deliberately has no owner/user field (ownership comes exclusively
    from Depends(get_owned_reading), never from client input) and no
    draw_order field (computed server-side as
    max(existing draw_order) + 1 by
    app/services/reading_service.py::record_card_draw() -- see
    Documentation/CARDDRAW_API_DESIGN.md Section 4.3). `extra="forbid"`
    (inherited from _Model) rejects both as 422 if a client attempts to
    supply either.
    """

    position_id: UUID
    card_id: UUID
    orientation: Orientation


class CardDrawSummary(_Model):
    """The smallest useful representation of a newly recorded CardDraw
    (Documentation/CARDDRAW_API_DESIGN.md Section 4.2) -- derived
    directly from CardDraw's own columns, plus one field that does not
    live on CardDraw itself: reading_status, the owning Reading's status
    immediately after this draw was recorded. Included because no
    GET /readings/{reading_id} route exists to check this separately
    (Section 2.7/4.2 of the same document) -- without it, a client would
    have no way to learn whether this draw just completed the spread.
    Deliberately omits card/position display names (e.g. card_name,
    position_name) -- an explicitly named, deferred question (Section 12
    of the same document), not decided by adding it here.
    """

    id: UUID
    position_id: UUID
    card_id: UUID
    orientation: Orientation
    draw_order: int
    created_at: datetime
    reading_status: ReadingStatus


class ReadingCardDrawSummary(_Model):
    """One CardDraw within a Reading's full detail view (Step 43,
    Documentation/READING_DETAIL_API_DESIGN.md Section 4.3). Embeds the
    full SpreadPositionSummary/CardSummary (reused verbatim from
    app/schemas/reference_data_api.py, not duplicated) so the Spread
    Review screen has everything it needs without a second reference-
    data round trip.

    Distinct from CardDrawSummary above (the POST
    /readings/{reading_id}/draws response): that endpoint's caller
    already knows the position/card it just specified, so it
    deliberately omits display names; a Reading Detail fetch,
    reconstructing state after navigation with no such prior knowledge,
    has no such shortcut available.
    """

    id: UUID
    position: SpreadPositionSummary
    card: CardSummary
    orientation: Orientation
    draw_order: int
    created_at: datetime


class ReadingDetail(_Model):
    """Full Reading state for Reading Detail / Spread Review (Step 43,
    Documentation/READING_DETAIL_API_DESIGN.md Section 4.4) -- the
    smallest response that lets the frontend reconstruct a Reading's
    entire evidence state after navigation or reload, without direct
    database access.

    Deliberately excludes interpretation and narrative content -- both
    remain separate resources with their own existing routes (POST
    /readings/{reading_id}/interpret, GET .../interpretations(/current),
    GET .../narrative), preserving the evidence-vs-interpretation
    separation already established by
    Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1. A
    Reading may have zero, one, or many Interpretation rows (Q4,
    Documentation/PRODUCT_DECISIONS.md); this schema deliberately has no
    field that could imply otherwise.

    Excludes reflection_session_id/owner_id -- internal, no frontend
    meaning, never exposed by ReadingSummary either.

    Includes both `spread_id` (a direct scalar reference, parallel to
    `deck_id`) and the fully embedded `spread` -- Step 42's own design
    considered the bare id superseded by the embed; Step 43's
    implementation contract explicitly requested both, so both are
    included here rather than silently narrowing that instruction.
    """

    id: UUID
    status: ReadingStatus
    question: str
    question_domain: str | None
    draw_method: DrawMethod
    created_at: datetime
    updated_at: datetime
    spread_id: UUID
    spread: SpreadSummary
    deck_id: UUID
    card_draws: list[ReadingCardDrawSummary]
