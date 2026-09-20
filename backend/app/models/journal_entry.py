from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reading import Reading


class JournalEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A private, user-written reflection attached to one Reading
    (docs/NAMING_CONVENTIONS.md's "Journal" -- "A private record created
    by the user. Journal entries belong to the user and remain under
    their control.").

    FK'd directly to `reading_id` (not routed through ReflectionSession),
    mirroring Interpretation/AINarrative's own "FK to the thing it's
    about, ownership resolved by following that FK back to Reading"
    pattern -- no separate owner column here either; ownership is
    app/api/dependencies.py::get_owned_reading's job, exactly as for
    every other Reading-scoped resource.

    Deliberately append-only (no update/delete route) -- the smallest
    persistence layer that supports "write a reflection, see it again
    when you reopen this reading." A Reading may have any number of
    entries, ordered by `sequence` (see
    app/services/journal_service.py::list_journal_entries), the same way
    a real journal accumulates entries over time rather than being a
    single overwritable note.

    `sequence` is a globally unique, monotonically increasing,
    application-assigned integer -- the same device
    Interpretation.sequence/AINarrative.sequence already use, for the
    same reason (see Interpretation.sequence's own docstring):
    `created_at` alone is not a reliable ordering key on SQLite
    (second-level `CURRENT_TIMESTAMP` resolution), which matters here
    more than it does for Interpretation/AINarrative -- a user can easily
    write two journal entries within the same second, and unlike those
    two models' "current row wins" semantics, every JournalEntry is
    individually displayed, in write order.
    """

    __tablename__ = "journal_entries"

    reading_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    reading: Mapped["Reading"] = relationship()

    @validates("content")
    def validate_content(self, _key: str, value: str) -> str:
        """Defense-in-depth behind JournalEntryCreate's own schema-level
        guard (app/schemas/journal.py), mirroring
        Reading.validate_question()'s exact rule and rationale.
        """
        if not value or not value.strip():
            raise ValueError("content must not be empty")
        return value
