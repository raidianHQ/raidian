from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.card import Card


class CardCorrespondence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Astrological / elemental correspondence data for a Card, from an
    external correspondence tradition -- deliberately kept separate from
    Card's own RWS meaning fields (base_meaning_upright/reversed, keywords,
    themes), which are Raidian Wise's own original-wording content.

    See Documentation/RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md and
    RAIDIAN_WISE_REFERENCE_DATA_V1.md (Section 8) for sourcing, the
    corrections applied to the source spreadsheet, and why this is a
    related table rather than columns on Card.

    One-to-one with Card for now (unique card_id); kept as its own table
    rather than columns on Card specifically so a second correspondence
    tradition could be added later without reshaping Card.
    """

    __tablename__ = "card_correspondences"

    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    tradition_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    element: Mapped[str] = mapped_column(String(20), nullable=False)
    zodiac_signs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    zodiac_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    astrological_influence: Mapped[str] = mapped_column(String(255), nullable=False)
    elemental_gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    animal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    astrology_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    card: Mapped["Card"] = relationship(back_populates="correspondence")
