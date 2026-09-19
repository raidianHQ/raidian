from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reading import Reading
    from app.models.user import User


class ReflectionSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The overall reflective experience a user engages in.

    A Reflection Session may in the future wrap other reflective activities
    (journaling, Scripture study) alongside tarot. Raidian Wise Phase 1 only
    implements its tarot portion -- the Reading -- so this model is
    intentionally minimal: identity, timestamps, and (Step 22) ownership
    only. It is not a dumping ground for fields that belong to Reading.

    owner_id is the ownership anchor for a Reading and, transitively,
    every resource beneath it (CardDraw, Interpretation; NarrativeModel
    is never persisted at all) -- placed here rather than on Reading per
    Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md Section 2.5
    (grounded in ADR-0003's "modular and extensible" platform-identity
    rationale), and reached from a Reading through the existing 1:1
    Reading.reflection_session_id relationship. None of those child
    resources carries an owner column of its own; ownership is always
    resolved by following this one column back through the owning
    Reading, never duplicated or re-derived elsewhere.

    Every Reading created through POST /readings
    (app/services/reading_service.py::create_reading(), Step 27)
    receives its owner directly from the authenticated current_user at
    construction time -- ownership is established once, at Reading/
    ReflectionSession creation, and is never reassigned afterward.
    Nullable because a ReflectionSession can still be constructed
    without an owner outside that path (test fixtures do this
    deliberately); app.api.dependencies.get_owned_reading treats a NULL
    owner_id as inaccessible to every authenticated caller, so no
    NOT NULL constraint is required for that case to remain safe.
    """

    __tablename__ = "reflection_sessions"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    reading: Mapped["Reading | None"] = relationship(
        back_populates="reflection_session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    owner: Mapped["User | None"] = relationship(back_populates="reflection_sessions")
