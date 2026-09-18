from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_type
from app.models.enums import Orientation

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.reading import Reading
    from app.models.spread_position import SpreadPosition


class CardDraw(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The historical record of a card actually drawn in a Reading.

    This is deliberately separate from Card (what a card *is*): Card is
    deck-level reference data, reusable across every Reading; CardDraw is the
    immutable per-Reading fact of what was drawn, in which position, in what
    orientation, and in what order. Reinterpreting a Reading later must never
    alter CardDraw rows.
    """

    __tablename__ = "card_draws"
    __table_args__ = (
        UniqueConstraint(
            "reading_id", "position_id", name="uq_card_draws_reading_id_position_id"
        ),
        UniqueConstraint(
            "reading_id", "draw_order", name="uq_card_draws_reading_id_draw_order"
        ),
        CheckConstraint("draw_order >= 1", name="ck_card_draws_draw_order_positive"),
    )

    reading_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spread_positions.id", ondelete="RESTRICT"), nullable=False
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False
    )

    orientation: Mapped[Orientation] = mapped_column(
        str_enum_type(Orientation, name="orientation", length=20), nullable=False
    )
    draw_order: Mapped[int] = mapped_column(Integer, nullable=False)

    reading: Mapped["Reading"] = relationship(back_populates="card_draws")
    position: Mapped["SpreadPosition"] = relationship(back_populates="card_draws")
    card: Mapped["Card"] = relationship(back_populates="card_draws")
