from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.reading import Reading


class Deck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A tarot card deck (e.g. Rider-Waite-Smith).

    MVP ships with a single deck, but the schema is deck-agnostic so
    additional decks can be added later without structural change.
    """

    __tablename__ = "decks"
    __table_args__ = (UniqueConstraint("name", name="uq_decks_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cards: Mapped[list["Card"]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )
    readings: Mapped[list["Reading"]] = relationship(back_populates="deck")
