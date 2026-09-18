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

    owner_id is the ownership anchor for a Reading and everything beneath
    it (CardDraw, Interpretation) -- placed here rather than on Reading
    per Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md Section 2.5
    (grounded in ADR-0003's "modular and extensible" platform-identity
    rationale). Nullable because no Reading/ReflectionSession-creation API
    exists yet (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 4.4) -- there is currently no code path that could supply a
    value at insert time. A future Reading-creation route must set it from
    the authenticated caller; not built here (Step 22 scope).
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
