"""Journal entry persistence -- the smallest layer needed for "write a
private reflection, see it again when you reopen this reading"
(docs/NAMING_CONVENTIONS.md's "Journal"). Deliberately its own module
(mirrors reading_service.py's own scope), not folded into
reading_orchestration.py: journaling has nothing to do with the
Interpretation Engine / Narrative / Scripture / AI Narrative pipeline that
module exists to coordinate -- a JournalEntry is a plain, independent
child of Reading, the same relationship shape as CardDraw.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.journal_entry import JournalEntry
from app.models.reading import Reading


def _next_sequence(session: Session) -> int:
    """Mirrors interpretation/persistence.py::_next_sequence -- a global,
    not per-reading, monotonic counter. See JournalEntry.sequence's own
    docstring for why.
    """
    current_max = session.execute(select(func.max(JournalEntry.sequence))).scalar()
    return (current_max or 0) + 1


def create_journal_entry(session: Session, reading: Reading, *, content: str) -> JournalEntry:
    """Does not commit -- the caller controls the transaction boundary,
    exactly as reading_service.py's own mutations do.
    """
    entry = JournalEntry(reading=reading, content=content, sequence=_next_sequence(session))
    session.add(entry)
    session.flush()
    return entry


def list_journal_entries(session: Session, reading: Reading) -> list[JournalEntry]:
    """Every JournalEntry for `reading`, oldest-first (ascending
    `sequence`) -- a journal is read in the order it was written, unlike
    Interpretation/AINarrative history (which surface newest-first, since
    those represent successive *replacements* of "the current one" rather
    than an accumulating personal record).
    """
    return list(
        session.execute(
            select(JournalEntry)
            .where(JournalEntry.reading_id == reading.id)
            .order_by(JournalEntry.sequence)
        ).scalars()
    )
