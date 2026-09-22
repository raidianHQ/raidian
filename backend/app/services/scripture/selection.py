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

Matching a candidate theme to approved references is never a fuzzy or
generic "similar word" lookup -- it is either an exact tag match, or a
small, explicit, hand-reviewed relation to one other tag curated in
_RELATED_THEMES below (for example discernment/clarity). Both are
"approved mapping" in the same sense: a human reviewer decided the
reference applies. What this module will never do is match on a theme
merely *containing* similar words, or invent a reference that is not
already a real row in the approved dataset.

select_scripture_reflections() processes *every* candidate theme in
_theme_candidates() order (never just the first one with a match) and
returns the union of what each candidate's cluster legitimately turns up
-- still capped per candidate (_MAX_REFLECTIONS), still deduplicated by
the underlying ScriptureReference row so the same approved reference is
never listed twice, and still ordered candidate-by-candidate in that same
priority order, so a reading touching several Scripture-mapped themes
(a plausible outcome for both Single Card and multi-card readings alike
-- see _theme_for_scripture) can surface all of them, grouped by theme
in priority order, rather than only its single highest-priority match.

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
"""Keeps any one candidate theme's own contribution focused -- mirrors
app/services/interpretation/engine.py's own _SUPPORTING_THEMES_LIMIT
precedent. A **per-candidate** cap: bounds how many approved references
one candidate stage (see _theme_for_scripture below) contributes, across
every theme in that stage's own cluster (see _RELATED_THEMES) -- rows
beyond this cap for that one candidate are simply left out, in
ScriptureReference's own book/chapter/verse order. There is deliberately
no separate cap on the *total* returned across every candidate
combined -- select_scripture_reflections() now processes every candidate
in _theme_candidates() (not just the first one with any match), so a
reading that legitimately touches several Scripture-mapped themes can
return more than _MAX_REFLECTIONS reflections in total, one bounded
group per theme.
"""

_RELATED_THEMES: dict[str, tuple[str, ...]] = {
    "discernment": ("clarity",),
    "clarity": ("discernment",),
}
"""A small, explicit, hand-reviewed table of theme pairs close enough in
meaning that one theme's approved Scripture references are also a
legitimate match for the other -- never fuzzy text/keyword matching (see
_theme_cluster below), and never a substitute for a theme having its own
real, verifiable reference when one exists. Each pair here is a deliberate
content decision, the same way an entry in scripture_references.yaml
itself is -- not a generic "synonym" or "related word" lookup.

Seeded with discernment/clarity: theme_vocabulary.yaml already groups
these two under one heading ("Clarity & discernment"), and Raidian's own
authored card content already treats them as one cluster -- Queen of
Swords (rider_waite_smith/swords.yaml) lists `discernment` as a primary
theme and `clarity` as a secondary theme of the very same card. This is
the strongest available evidence that the relationship is genuine rather
than invented for this feature.

Kept intentionally tiny and symmetric (each pair listed both directions)
rather than solved generically (e.g. via embeddings or free-text
similarity) -- see this module's own docstring for why a broader,
automatic notion of "similar" is deliberately out of scope here. Adding
another pair is a content decision for a human reviewer, exactly like
adding a new scripture_references.yaml entry.
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
    """Ordered themes select_scripture_reflections() checks, *every one*
    of them, in this priority order: 1) the reading's primary Scripture
    theme (_theme_for_scripture above), 2) each already-ranked
    `supporting_themes` entry, then 3) `clarification`, 4) `blocker`, and
    5) `advice` (each already a single structurally-selected theme tag on
    InterpretiveModel, used only when present -- all three default to
    None and are skipped when unset). Never a Card/CardDraw lookup of its
    own -- this only widens *which* already-computed theme(s) get
    checked, never where a theme tag comes from. De-duplicates so the
    same theme is never queried twice.
    """
    candidates = [
        _theme_for_scripture(model),
        *(explained.value for explained in model.supporting_themes),
    ]
    for explained in (model.clarification, model.blocker, model.advice):
        if explained is not None:
            candidates.append(explained.value)

    seen: set[str] = set()
    ordered: list[str] = []
    for theme in candidates:
        if theme not in seen:
            seen.add(theme)
            ordered.append(theme)
    return tuple(ordered)


def _theme_cluster(theme: str) -> tuple[str, ...]:
    """`theme` itself, plus any theme(s) _RELATED_THEMES curates as close
    enough in meaning to also be a legitimate match -- e.g.
    `_theme_cluster("discernment") == ("discernment", "clarity")`. Always
    starts with `theme` itself so a direct, explicitly-mapped reference is
    never reordered behind a related one. One hop only (a related theme's
    own related themes are not chased transitively) -- keeps this a small,
    auditable, hand-reviewed relation rather than an open-ended graph
    walk.
    """
    cluster = [theme]
    for related in _RELATED_THEMES.get(theme, ()):
        if related not in cluster:
            cluster.append(related)
    return tuple(cluster)


def _citations_for_theme(model: InterpretiveModel, theme: str) -> tuple[Citation, ...]:
    """Citations for whichever theme _theme_candidates() selected --
    copied verbatim from wherever that theme's own Explained[str]
    wrapper already lives on InterpretiveModel (central_issue,
    supporting_themes, clarification, blocker, and advice each already
    carry their own citations), never recomputed. Falls back to
    theme_strength only for the Single Card path's bare `themes[0]`
    string (see _theme_for_scripture), which has no Explained wrapper of
    its own -- the same lookup this function used exclusively before
    clarification/blocker/advice became candidates too.
    """
    if model.central_issue.value == theme:
        return model.central_issue.citations
    for explained in model.supporting_themes:
        if explained.value == theme:
            return explained.citations
    for explained in (model.clarification, model.blocker, model.advice):
        if explained is not None and explained.value == theme:
            return explained.citations
    return next((score.citations for score in model.theme_strength if score.theme == theme), ())


def select_scripture_reflections(session: Session, model: InterpretiveModel) -> ScripturalPerspective:
    """Maps the reading to approved ScriptureReference rows across
    *every* candidate theme in _theme_candidates() order -- the reading's
    primary Scripture theme, then its already-ranked supporting_themes,
    then clarification, blocker, and advice (Scripture Theme-Selection
    Design Audit, Section 3C, as amended to allow a ranked fallback, and
    further amended to allow every candidate with an approved mapping to
    contribute rather than only the first). For each candidate, in that
    priority order, its own cluster (see _theme_cluster: the theme
    itself, plus any theme _RELATED_THEMES curates as closely related to
    it) contributes up to _MAX_REFLECTIONS of its own approved rows.
    A reference already contributed by an earlier, higher-priority
    candidate is never repeated for a later one -- deduplicated by the
    underlying ScriptureReference row, not merely by theme, since two
    different candidates' clusters can legitimately overlap (e.g. a
    "discernment" candidate and a later, separately-ranked "clarity"
    candidate). There is no cap on the total across every candidate
    combined; a reading touching several Scripture-mapped themes returns
    all of them, still grouped candidate-by-candidate in priority order.
    If no candidate's cluster has an approved mapping, returns an empty
    perspective.
    """
    reflections: list[ScriptureReflection] = []
    seen_reference_ids: set = set()

    for theme in _theme_candidates(model):
        rows = session.scalars(
            select(ScriptureReference)
            .where(ScriptureReference.theme.in_(_theme_cluster(theme)))
            .order_by(ScriptureReference.book, ScriptureReference.chapter, ScriptureReference.verse_start)
        ).all()[:_MAX_REFLECTIONS]
        new_rows = [row for row in rows if row.id not in seen_reference_ids]
        if not new_rows:
            continue
        theme_citations = _citations_for_theme(model, theme)
        for row in new_rows:
            seen_reference_ids.add(row.id)
            reflections.append(_to_reflection(row, theme_citations))

    return ScripturalPerspective(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc),
        source_schema_version=model.schema_version,
        reflections=tuple(reflections),
    )
