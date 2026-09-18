"""Response envelope schemas for the Interpretation API (Step 11).

Wrap Interpretation's own row-level provenance fields (id, sequence,
created_at -- none of which live inside InterpretiveModel itself, since the
engine has no concept of its own database row) around the
InterpretiveModel schema returned unmodified elsewhere. See
Documentation/INTERPRETATION_API_DESIGN.md Section 3.2/10.

Pure data shape, no computation -- mirrors interpretive_model.py's and
narrative_model.py's own discipline. The actual construction of these from
an Interpretation ORM row happens in app/api/interpretation.py, not here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.interpretive_model import InterpretiveModel


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class InterpretationSummary(_Model):
    """Full interpretation content plus its row-level provenance.

    Returned by POST /readings/{id}/interpret and
    GET /readings/{id}/interpretations/current
    (INTERPRETATION_API_DESIGN.md Section 3.2) -- interpretive_model is
    embedded verbatim, never re-shaped or filtered.
    """

    id: UUID
    reading_id: UUID
    sequence: int
    engine_version: str
    reference_data_version: str
    created_at: datetime
    interpretive_model: InterpretiveModel


class InterpretationHistoryEntry(_Model):
    """One lightweight entry in GET /readings/{id}/interpretations.

    Deliberately omits the full InterpretiveModel -- a history list
    returning every past interpretation's complete structured content
    would grow roughly linearly with reinterpretation count for no benefit
    a history *list* view needs (INTERPRETATION_API_DESIGN.md Section 12).
    GET .../interpretations/current remains the place to retrieve full
    content for the current interpretation.
    """

    id: UUID
    sequence: int
    engine_version: str
    reference_data_version: str
    created_at: datetime
