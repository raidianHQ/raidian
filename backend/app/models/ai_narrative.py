from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interpretation import Interpretation


class AINarrative(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Reflection Engine (ADR-0005) generation run against a specific
    Interpretation -- mirrors app/models/interpretation.py::Interpretation's
    own relationship-not-columns, one-to-many, sequence-ordered design
    exactly, one layer over: Interpretation is to Reading as AINarrative is
    to Interpretation.

    FK'd to `interpretation_id` (not `reading_id`) deliberately: an
    AINarrative is a generation run against one specific, already-frozen
    InterpretiveModel snapshot. Reinterpreting a Reading creates a new
    Interpretation row (Interpretation's own docstring) without touching
    or deleting this one -- "the current AI narrative for this reading" is
    therefore "the highest-sequence AINarrative row for the *current*
    interpretation_id", not a reading-wide lookup, so a stale AI narrative
    generated against a since-superseded interpretation is never surfaced
    as current (see reading_orchestration.py::get_current_ai_narrative_for_reading).

    `sequence` is the same globally-unique, monotonically increasing,
    application-assigned integer as Interpretation.sequence, for the same
    reason (see that column's own docstring) -- re-generating (this
    project deliberately does not attempt to deduplicate/cache AI output,
    see AI_NARRATIVE_LAYER_DESIGN.md Section 5) creates a new row rather
    than overwriting the previous attempt, preserving generation history.

    `ai_narrative` stores app.schemas.ai_narrative.AINarrativeResponse,
    serialized via `.model_dump(mode="json")` -- the same
    parse-to-Pydantic/store-as-JSON/reconstruct-via-model_validate
    discipline as Interpretation.interpretive_model.
    """

    __tablename__ = "ai_narratives"

    interpretation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interpretations.id", ondelete="CASCADE"), nullable=False
    )

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    ai_narrative: Mapped[dict] = mapped_column(JSON, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    interpretation: Mapped["Interpretation"] = relationship()
