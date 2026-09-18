from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reading import Reading
    from app.models.spread_position import SpreadPosition


class Spread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A reusable spread definition (e.g. Single Card, Three Card, Celtic Cross).

    A Spread defines positions only -- it never contains actual drawn cards.
    See CardDraw for the record of what was actually drawn in a Reading.
    """

    __tablename__ = "spreads"
    __table_args__ = (UniqueConstraint("name", name="uq_spreads_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_duplicate_cards: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    positions: Mapped[list["SpreadPosition"]] = relationship(
        back_populates="spread",
        cascade="all, delete-orphan",
        order_by="SpreadPosition.position_order",
    )
    readings: Mapped[list["Reading"]] = relationship(back_populates="spread")

    @property
    def position_count(self) -> int:
        """Derived from the actual positions rather than stored, so it can never drift."""
        return len(self.positions)
