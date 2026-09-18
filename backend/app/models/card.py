from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_type
from app.models.enums import Arcana, Suit

if TYPE_CHECKING:
    from app.models.card_draw import CardDraw
    from app.models.deck import Deck


class Card(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A card definition within a Deck -- what the card *is*.

    Independent of any specific Reading. The historical record of what was
    actually drawn during a Reading lives on CardDraw, never here.
    """

    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("deck_id", "name", name="uq_cards_deck_id_name"),
        CheckConstraint(
            "(arcana = 'major' AND suit IS NULL) OR (arcana = 'minor' AND suit IS NOT NULL)",
            name="ck_cards_suit_matches_arcana",
        ),
    )

    deck_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decks.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    arcana: Mapped[Arcana] = mapped_column(
        str_enum_type(Arcana, name="arcana", length=20), nullable=False
    )
    suit: Mapped[Suit | None] = mapped_column(
        str_enum_type(Suit, name="suit", length=20), nullable=True
    )
    rank: Mapped[str | None] = mapped_column(String(20), nullable=True)
    image_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_meaning_upright: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_meaning_reversed: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    primary_themes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    secondary_themes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    deck: Mapped["Deck"] = relationship(back_populates="cards")
    card_draws: Mapped[list["CardDraw"]] = relationship(back_populates="card")
