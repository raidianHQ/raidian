from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_type
from app.models.enums import SemanticRole

if TYPE_CHECKING:
    from app.models.card_draw import CardDraw
    from app.models.spread import Spread


class SpreadPosition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single position within a Spread (e.g. "Situation", "Advice")."""

    __tablename__ = "spread_positions"
    __table_args__ = (
        UniqueConstraint(
            "spread_id", "position_order", name="uq_spread_positions_spread_id_position_order"
        ),
        CheckConstraint("position_order >= 1", name="ck_spread_positions_position_order_positive"),
    )

    spread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spreads.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_order: Mapped[int] = mapped_column(Integer, nullable=False)
    semantic_role: Mapped[SemanticRole] = mapped_column(
        str_enum_type(SemanticRole, name="semantic_role", length=30),
        nullable=False,
        default=SemanticRole.GENERAL,
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    spread: Mapped["Spread"] = relationship(back_populates="positions")
    card_draws: Mapped[list["CardDraw"]] = relationship(back_populates="position")
