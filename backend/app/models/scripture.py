from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScriptureReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One approved Scripture reference for the optional Scriptural
    Reflection layer (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15) --
    reference data, deliberately separate from Card/CardCorrespondence.

    Keyed by `theme`, never by `Card` -- Scripture responds only to the
    theme layer the Interpretation Engine already establishes
    (`theme_strength`/`central_issue`/`supporting_themes`), never to a
    card directly ("explicitly not: Card -> God's message", Section 15).
    `theme` must be a tag that already exists in the canonical
    `theme_vocabulary.yaml` (enforced at load time, app/seed/loader.py --
    mirrors how Card.primary_themes/secondary_themes reuse that same
    vocabulary rather than each maintaining an independent one).

    No passage TEXT is stored here -- only the reference itself
    (book/chapter/verse) plus short, original commentary written for this
    project (`context_note`, `reflection_connection`), per Section 15.1's
    licensing constraint: "Do not embed copyrighted Bible translation
    text in the MVP." `translation` names which public-domain translation
    this reference/citation would be labeled under if translation text is
    ever shown -- it is never resolved to actual verse text today (Q5,
    Section 16, remains open); approved values are enforced at load time
    (app/seed/loader.py's APPROVED_SCRIPTURE_TRANSLATIONS), not as a DB
    enum, mirroring how CardCorrespondence.element/direction (a similarly
    small, closed, externally-sourced vocabulary) are plain validated
    String columns rather than DB-level enums.
    """

    __tablename__ = "scripture_references"
    __table_args__ = (
        UniqueConstraint(
            "theme", "book", "chapter", "verse_start", "translation",
            name="uq_scripture_references_theme_book_chapter_verse_translation",
        ),
        CheckConstraint("chapter >= 1", name="ck_scripture_references_chapter_positive"),
        CheckConstraint("verse_start >= 1", name="ck_scripture_references_verse_start_positive"),
        CheckConstraint(
            "verse_end IS NULL OR verse_end >= verse_start",
            name="ck_scripture_references_verse_end_after_start",
        ),
    )

    theme: Mapped[str] = mapped_column(String(60), nullable=False)
    book: Mapped[str] = mapped_column(String(30), nullable=False)
    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_start: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_display: Mapped[str] = mapped_column(String(60), nullable=False)
    translation: Mapped[str] = mapped_column(String(10), nullable=False)
    context_note: Mapped[str] = mapped_column(Text, nullable=False)
    reflection_connection: Mapped[str] = mapped_column(Text, nullable=False)
