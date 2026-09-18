from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_type
from app.models.enums import DrawMethod, Orientation, ReadingStatus
from app.models.exceptions import DuplicateCardError

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.card_draw import CardDraw
    from app.models.deck import Deck
    from app.models.interpretation import Interpretation
    from app.models.reflection_session import ReflectionSession
    from app.models.spread import Spread
    from app.models.spread_position import SpreadPosition


class Reading(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The tarot portion of a Reflection Session.

    Preserves the original reading evidence -- question, spread, deck, draw
    method, and (via CardDraw) the cards actually drawn -- independent of any
    future interpretation. See RAIDIAN_WISE_PRODUCT_SPEC_V1.md, Section 17
    (Versioning).
    """

    __tablename__ = "readings"

    reflection_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reflection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    spread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spreads.id", ondelete="RESTRICT"), nullable=False
    )
    deck_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decks.id", ondelete="RESTRICT"), nullable=False
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_domain: Mapped[str | None] = mapped_column(String(60), nullable=True)
    draw_method: Mapped[DrawMethod] = mapped_column(
        str_enum_type(DrawMethod, name="draw_method", length=20),
        nullable=False,
        default=DrawMethod.PHYSICAL,
    )
    status: Mapped[ReadingStatus] = mapped_column(
        str_enum_type(ReadingStatus, name="reading_status", length=20),
        nullable=False,
        default=ReadingStatus.DRAFTING,
    )

    reflection_session: Mapped["ReflectionSession"] = relationship(back_populates="reading")
    spread: Mapped["Spread"] = relationship(back_populates="readings")
    deck: Mapped["Deck"] = relationship(back_populates="readings")
    card_draws: Mapped[list["CardDraw"]] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
        order_by="CardDraw.draw_order",
    )
    interpretations: Mapped[list["Interpretation"]] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
        order_by="Interpretation.sequence",
    )

    @property
    def is_spread_complete(self) -> bool:
        """Whether every required SpreadPosition on this Reading's Spread
        has a drawn card -- the precondition
        app/services/reading_orchestration.py's interpret_reading() checks
        before invoking the Interpretation Engine at all
        (Documentation/READING_INTEGRATION_DESIGN.md Section 3). Derived
        rather than stored, so it can never drift (the same "derive, don't
        store-and-risk-drift" precedent as Spread.position_count).
        """
        required_position_ids = {p.id for p in self.spread.positions if p.required}
        drawn_position_ids = {d.position_id for d in self.card_draws}
        return required_position_ids.issubset(drawn_position_ids)

    @validates("question")
    def validate_question(self, _key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("question must not be empty")
        return value

    def add_card_draw(
        self,
        *,
        position: "SpreadPosition",
        card: "Card",
        orientation: Orientation,
        draw_order: int,
    ) -> "CardDraw":
        """Record a drawn card, enforcing the invariants a raw insert wouldn't:

        - the position must belong to this reading's spread
        - the card must belong to this reading's deck
        - duplicate cards are rejected unless the spread explicitly allows them
        """
        from app.models.card_draw import CardDraw

        if position.spread_id != self.spread_id:
            raise ValueError("position does not belong to this reading's spread")
        if card.deck_id != self.deck_id:
            raise ValueError("card does not belong to this reading's deck")
        if not self.spread.allow_duplicate_cards and any(
            existing.card_id == card.id for existing in self.card_draws
        ):
            raise DuplicateCardError(
                f"card {card.id} has already been drawn in this reading"
            )

        draw = CardDraw(
            position=position, card=card, orientation=orientation, draw_order=draw_order
        )
        self.card_draws.append(draw)
        return draw
