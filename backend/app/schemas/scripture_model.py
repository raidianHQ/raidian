"""The structured, deterministic output contract of the optional
Scriptural Reflection layer (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md
Section 15).

Deliberately its own module, separate from interpretive_model.py --
Scripture is an additional, optional perspective layered ON TOP of a
tarot Interpretation, never a field of InterpretiveModel itself (Section
15: "conceptually and architecturally separate from tarot
interpretation... explicitly not: Card -> God's message"). Pure data
shape, no computation -- mirrors interpretive_model.py's and
narrative_model.py's own discipline.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.interpretive_model import Citation


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


DISCLAIMER = (
    "Scripture is offered here as an optional source of reflection, not as "
    "proof that this reading -- or any card in it -- represents God's will. "
    "These references respond to the reading's themes, never to a card "
    "directly, and are not a substitute for one's own study, prayer, or "
    "pastoral guidance."
)
"""Fixed guardrail text (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15 /
docs/PROJECT_VISION.md's "Scripture Integration" section: "does not claim
that scripture validates a card reading"). Part of the template, not
derived from data -- always attached via ScripturalPerspective's own
default, never optional-to-omit at a construction site.
"""


class ScriptureReflection(_Model):
    """One theme's approved Scripture reference and original commentary.

    No passage text is carried here -- `reference_display`/`translation`
    are a citation only (Section 15.1's licensing constraint); `book`/
    `chapter`/`verse_start`/`verse_end` are the same reference in
    structured form. `context_note` and `reflection_connection` are
    original commentary written for this project, never a quotation.

    `theme_citations` point back to the specific drawn cards/positions in
    the reading that established `theme` -- copied verbatim from the
    source InterpretiveModel's own `theme_strength` entry, never
    recomputed -- so this reflection is traceable to real evidence in
    the reading, not merely to a theme tag in the abstract.
    """

    theme: str
    book: str
    chapter: int
    verse_start: int
    verse_end: int | None
    reference_display: str
    translation: str
    context_note: str
    reflection_connection: str
    theme_citations: tuple[Citation, ...] = Field(min_length=1)


class ScripturalPerspective(_Model):
    """The complete, deterministic Scriptural Reflection for one
    Interpretation -- entirely optional and additional to it. This shape
    itself is still just data (no computation lives here) -- selection
    logic remains in app/services/scripture/selection.py.

    Once selected for a given Interpretation and found to contain at
    least one reflection, this is persisted as a
    app.models.scriptural_reflection.ScripturalReflection snapshot (see
    app/services/reading_orchestration.py::get_scripture_for_reading) so
    a saved/reopened reading shows the same Scriptural Reflection it
    originally displayed, rather than silently re-deriving it from a
    Scripture reference dataset that may have changed since. An empty
    `reflections` tuple is a valid, expected outcome, not an error --
    it is deliberately never persisted, so a reading whose themes have no
    approved mapping yet can still pick one up later if the approved
    dataset grows (this foundation seeds only a small subset of the
    Interpretation Engine's own theme vocabulary).
    """

    schema_version: str
    generated_at: datetime
    source_schema_version: str
    disclaimer: str = DISCLAIMER
    reflections: tuple[ScriptureReflection, ...] = ()
