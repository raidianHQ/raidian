"""Deterministic theme -> Scripture reference selection
(Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15).

Reads only InterpretiveModel.theme_strength (already-computed,
already-cited themes from the deterministic Interpretation Engine) plus
the approved ScriptureReference reference-data table -- never a Card,
CardDraw, or any other tarot evidence row directly, and never an LLM or
any other generative call. This keeps Scripture strictly downstream of,
and separate from, the tarot engine's own source-of-truth meanings
(app/services/interpretation/) -- the same "pure downstream
transformation" discipline app/services/narrative/ already applies,
except this layer needs a database session to look up approved
references, so it is not itself fully DB-free the way narrative/ is.

Never mutates `model` (InterpretiveModel is frozen -- mutation is not
possible even by accident) and never writes to the database -- read-only
with respect to both the Reading's evidence and the Interpretation's own
content.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scripture import ScriptureReference
from app.schemas.interpretive_model import Citation, InterpretiveModel
from app.schemas.scripture_model import ScripturalPerspective, ScriptureReflection

SCHEMA_VERSION = "1.0"

_MAX_REFLECTIONS = 3
"""Keeps the perspective focused -- mirrors
app/services/interpretation/engine.py's own _SUPPORTING_THEMES_LIMIT
precedent. Not a ranking judgment of its own: themes are still consumed
in theme_strength's own already-approved count-desc/name-asc order
(meanings.py Rule T1), so the most evidence-backed themes in the reading
get first claim on this limit.
"""


def _to_reflection(row: ScriptureReference, theme_citations: tuple[Citation, ...]) -> ScriptureReflection:
    return ScriptureReflection(
        theme=row.theme,
        book=row.book,
        chapter=row.chapter,
        verse_start=row.verse_start,
        verse_end=row.verse_end,
        reference_display=row.reference_display,
        translation=row.translation,
        context_note=row.context_note,
        reflection_connection=row.reflection_connection,
        theme_citations=theme_citations,
    )


def select_scripture_reflections(session: Session, model: InterpretiveModel) -> ScripturalPerspective:
    """Deterministically maps `model.theme_strength` to approved
    ScriptureReference rows via an exact theme-tag match -- no fuzzy
    matching, no invented equivalence, no scoring beyond theme_strength's
    own existing order. A theme with no approved mapping simply
    contributes no reflection; this is the expected, non-error outcome
    for most themes today (this foundation seeds only a small subset of
    the shared theme vocabulary) -- see ScripturalPerspective's own
    docstring.
    """
    reflections: list[ScriptureReflection] = []
    for theme_score in model.theme_strength:
        if len(reflections) >= _MAX_REFLECTIONS:
            break
        rows = session.scalars(
            select(ScriptureReference)
            .where(ScriptureReference.theme == theme_score.theme)
            .order_by(ScriptureReference.book, ScriptureReference.chapter, ScriptureReference.verse_start)
        ).all()
        for row in rows:
            if len(reflections) >= _MAX_REFLECTIONS:
                break
            reflections.append(_to_reflection(row, theme_score.citations))

    return ScripturalPerspective(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc),
        source_schema_version=model.schema_version,
        reflections=tuple(reflections),
    )
