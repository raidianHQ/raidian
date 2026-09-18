from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reading import Reading


class ReflectionSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The overall reflective experience a user engages in.

    A Reflection Session may in the future wrap other reflective activities
    (journaling, Scripture study) alongside tarot. Raidian Wise Phase 1 only
    implements its tarot portion -- the Reading -- so this model is
    intentionally minimal: identity and timestamps only. It is not a
    dumping ground for fields that belong to Reading.
    """

    __tablename__ = "reflection_sessions"

    reading: Mapped["Reading | None"] = relationship(
        back_populates="reflection_session",
        uselist=False,
        cascade="all, delete-orphan",
    )
