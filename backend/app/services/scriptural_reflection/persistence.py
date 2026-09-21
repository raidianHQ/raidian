"""Persists an already-selected ScripturalPerspective snapshot.
Deliberately separate from app/services/scripture/selection.py (which
performs the actual theme -> ScriptureReference matching and never
touches the database for writes) -- mirrors
app/services/ai_narrative/persistence.py's own compute-vs-persist split
exactly, applied to the deterministic Scripture layer instead of the AI
Narrative layer.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interpretation import Interpretation
from app.models.scriptural_reflection import ScripturalReflection
from app.schemas.scripture_model import ScripturalPerspective


def _next_sequence(session: Session) -> int:
    """Mirrors ai_narrative/persistence.py::_next_sequence -- a global,
    not per-interpretation, monotonic counter. See
    ScripturalReflection.sequence's own docstring for why.
    """
    current_max = session.execute(select(func.max(ScripturalReflection.sequence))).scalar()
    return (current_max or 0) + 1


def save_scriptural_reflection(
    session: Session, interpretation: Interpretation, perspective: ScripturalPerspective
) -> ScripturalReflection:
    """Creates a new ScripturalReflection row for `interpretation`.

    Callers are expected to only call this when `perspective.reflections`
    is non-empty (see reading_orchestration.py::get_scripture_for_reading)
    -- this function itself performs no such check, mirroring
    save_ai_narrative()'s own "persistence trusts its caller's decision"
    contract.

    Does not commit -- the caller controls the transaction boundary
    (mirrors save_ai_narrative()'s own contract).
    """
    reflection = ScripturalReflection(
        interpretation=interpretation,
        scriptural_perspective=perspective.model_dump(mode="json"),
        sequence=_next_sequence(session),
    )
    session.add(reflection)
    session.flush()
    return reflection


def get_current_scriptural_reflection(
    session: Session, interpretation: Interpretation
) -> ScripturalReflection | None:
    """The ScripturalReflection row with the highest `sequence` for
    `interpretation`, or None if this specific interpretation has never
    had a snapshot persisted -- mirrors
    ai_narrative/persistence.py's sibling lookup in
    reading_orchestration.py::get_current_ai_narrative, one layer over.
    """
    return session.execute(
        select(ScripturalReflection)
        .where(ScripturalReflection.interpretation_id == interpretation.id)
        .order_by(ScripturalReflection.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
