"""User account model (Step 22).

The minimal identity/account entity this project has never had before --
see Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
Section 3. Deliberately excludes any profile, role, verification, or
password-reset field no governance document requires yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reflection_session import ReflectionSession


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An authenticated account.

    Owns zero or more ReflectionSessions -- and, transitively, every
    Reading/CardDraw/Interpretation beneath them -- via
    ReflectionSession.owner_id. Never referenced directly by any
    child-of-Reading table; ownership is always resolved through
    ReflectionSession (Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md
    Section 2.5, Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md Section 3).
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reflection_sessions: Mapped[list["ReflectionSession"]] = relationship(back_populates="owner")
