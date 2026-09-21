from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interpretation import Interpretation


class ScripturalReflection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One persisted Scriptural Reflection snapshot for a specific
    Interpretation -- mirrors app/models/ai_narrative.py::AINarrative's own
    relationship-not-columns, sequence-ordered design exactly, applied to
    the deterministic Scripture layer instead of the AI Narrative layer.

    FK'd to `interpretation_id` (not `reading_id`), for the same reason as
    AINarrative: a snapshot is a selection run against one specific,
    already-frozen InterpretiveModel. Reinterpreting a Reading creates a
    new Interpretation row without touching or deleting this one -- "the
    current Scriptural Reflection for this reading" is therefore "the
    highest-sequence ScripturalReflection row for the *current*
    interpretation_id", not a reading-wide lookup, so a stale snapshot
    generated against a since-superseded interpretation is never surfaced
    as current (see reading_orchestration.py::get_current_scriptural_reflection_for_reading).

    Deliberately only ever created when a selection found at least one
    approved reference (see
    app/services/reading_orchestration.py::get_scripture_for_reading) --
    an empty result is never persisted here, so a reading whose themes
    have no approved mapping yet is not permanently frozen at "no
    reference": a later addition to the approved ScriptureReference
    dataset can still surface on this reading's next explicit request.

    Unlike AINarrative, Scripture selection is a pure, deterministic
    function of already-persisted data (the frozen InterpretiveModel plus
    the approved ScriptureReference table) -- there is no product reason
    to "regenerate" it the way a stochastic AI call is regenerated. In
    practice this means at most one row exists per interpretation today.
    `sequence` exists anyway, for the same reliable-ordering reason
    Interpretation.sequence/AINarrative.sequence/JournalEntry.sequence
    already use (SQLite's second-resolution `CURRENT_TIMESTAMP` is not a
    safe tiebreak) and so "current" lookup uses the exact same shape as
    AINarrative's, without requiring a future change if a deliberate
    re-selection action is ever added.

    `scriptural_perspective` stores
    app.schemas.scripture_model.ScripturalPerspective, serialized via
    `.model_dump(mode="json")` -- the same parse-to-Pydantic/store-as-
    JSON/reconstruct-via-model_validate discipline as
    Interpretation.interpretive_model and AINarrative.ai_narrative.
    """

    __tablename__ = "scriptural_reflections"

    interpretation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interpretations.id", ondelete="CASCADE"), nullable=False
    )

    scriptural_perspective: Mapped[dict] = mapped_column(JSON, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    interpretation: Mapped["Interpretation"] = relationship()
