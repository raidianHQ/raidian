"""Deterministic theme -> Scripture reference selection
(Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15).

Reads a single theme -- for a Single Card reading, that card's own
first-listed authored theme; for two or more cards, the reading's own
already-computed InterpretiveModel.central_issue -- plus the approved
ScriptureReference reference-data table -- never a Card, CardDraw, or
any other tarot evidence row directly, and never an LLM or any other
generative call. See _theme_for_scripture() below (Scripture
Theme-Selection Design Audit, Option 2). This keeps Scripture strictly
downstream of, and separate from, the tarot engine's own source-of-truth
meanings (app/services/interpretation/) -- the same "pure downstream
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
precedent. Bounds how many approved references for the single selected
theme (see _theme_for_scripture below) are returned; it is no longer a
cross-theme allowance -- a theme with more than this many approved
references simply has the rest left out, in ScriptureReference's own
book/chapter/verse order.
"""


def _theme_for_scripture(model: InterpretiveModel) -> str:
    """The single theme Scripture selection responds to for this
    reading -- approved by the Scripture Theme-Selection Design Audit's
    Option 2. `central_issue` itself is never read from or written to
    here beyond the multi-card case below, so Narrative/AI-context text
    is completely unaffected by this choice.

    Single Card (exactly one drawn card): the card's own first-listed
    authored theme -- CardInterpretation.themes is already primary
    themes before secondary, deduped (see its own docstring), so
    `themes[0]` is that card's strongest authored theme, not whichever
    theme happens to sort alphabetically first among count=1 ties the
    way central_issue would pick for a single card.

    Two or more drawn cards: `central_issue.value` as-is -- the reading's
    own already-computed, already-cited central theme, unchanged.
    """
    if len(model.card_interpretations) == 1:
        return model.card_interpretations[0].themes[0]
    return model.central_issue.value


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


def _theme_candidates(model: InterpretiveModel) -> tuple[str, ...]:
    """Ordered themes select_scripture_reflections() tries in turn: the
    reading's primary Scripture theme (_theme_for_scripture above)
    first, then each already-ranked `supporting_themes` entry as a
    fallback -- tried only when every theme earlier in this order has no
    approved ScriptureReference. Still an exact, per-theme match with no
    fuzzy/invented equivalence; this only widens *which* theme(s) get
    checked, never how a single theme is matched. De-duplicates so the
    same theme is never queried twice.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for theme in (_theme_for_scripture(model), *(explained.value for explained in model.supporting_themes)):
        if theme not in seen:
            seen.add(theme)
            ordered.append(theme)
    return tuple(ordered)


def select_scripture_reflections(session: Session, model: InterpretiveModel) -> ScripturalPerspective:
    """Maps the reading to approved ScriptureReference rows for the
    first theme -- in _theme_candidates() order -- that has an approved
    mapping: the reading's primary Scripture theme first, then its
    already-ranked supporting_themes as a fallback (Scripture Theme-
    Selection Design Audit, Section 3C, as amended to allow a ranked
    fallback rather than none). Each candidate theme is still matched
    exactly, never fuzzily; the first candidate with any approved rows
    wins outright -- a later candidate is never merged in alongside it.
    If no candidate theme has an approved mapping, returns an empty
    perspective.
    """
    for theme in _theme_candidates(model):
        rows = session.scalars(
            select(ScriptureReference)
            .where(ScriptureReference.theme == theme)
            .order_by(ScriptureReference.book, ScriptureReference.chapter, ScriptureReference.verse_start)
        ).all()
        if rows:
            theme_citations: tuple[Citation, ...] = next(
                (score.citations for score in model.theme_strength if score.theme == theme),
                (),
            )
            reflections = tuple(_to_reflection(row, theme_citations) for row in rows[:_MAX_REFLECTIONS])
            break
    else:
        reflections = ()

    return ScripturalPerspective(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc),
        source_schema_version=model.schema_version,
        reflections=reflections,
    )
