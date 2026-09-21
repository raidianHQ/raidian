"""The Reading Integration orchestration layer (Step 9; extended Step 11;
extended again for the optional Scriptural Reflection layer; extended
again for the AI Narrative Layer).

The only module permitted to combine database access with calls into the
deterministic Interpretation Engine (app/services/interpretation/), the
deterministic, database-free Narrative Layer (app/services/narrative/),
the deterministic, database-backed Scripture Layer
(app/services/scripture/), and the AI Narrative Layer
(app/services/ai_narrative/, itself the only caller of the Reflection
Engine, app/services/reflection_engine/, per ADR-0005) -- mirrors the
loader/seed and compute/persist separations already established elsewhere
in this project. See Documentation/READING_INTEGRATION_DESIGN.md Section
13.

Scripture remains conceptually and architecturally separate from tarot
interpretation (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15) despite living
alongside Narrative in this one orchestration module -- that grouping is
purely about *where database access is permitted to happen* (this
module's own charter), not about Scripture being part of the tarot
engine's source-of-truth meanings. get_scripture_for_reading() below
never feeds anything back into interpret()/save_interpretation(), and
Scripture content is never merged into InterpretiveModel. The same is true
of the AI Narrative Layer, one level further out: generate_ai_narrative_for_reading()
below reads an already-persisted InterpretiveModel (and, optionally, an
already-computed ScripturalPerspective) and never feeds its own output
back into either.

Also the only module the Interpretation API (app/api/interpretation.py,
Step 11), the Scripture API (app/api/scripture.py), and the AI Narrative
API (app/api/ai_narrative.py) are permitted to call into for
Interpretation/Narrative/Scripture/AINarrative data -- the API layer must
never query Interpretation directly
(Documentation/INTERPRETATION_API_DESIGN.md Section 2.1/16).

None of these functions commit or roll back the session -- the caller
controls the transaction boundary
(Documentation/READING_INTEGRATION_DESIGN.md Section 14), exactly as
interpretation/persistence.py's own save_interpretation already does. For
the API, that caller is app/db/session.py's get_db() dependency.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_narrative import AINarrative
from app.models.interpretation import Interpretation
from app.models.reading import Reading
from app.schemas.ai_narrative import AINarrativeResponse
from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.narrative_model import NarrativeModel
from app.schemas.scripture_model import ScripturalPerspective
from app.services.ai_narrative.context import build_deterministic_reading_context
from app.services.ai_narrative.generation import generate_ai_narrative
from app.services.ai_narrative.persistence import save_ai_narrative
from app.services.interpretation.engine import interpret
from app.services.interpretation.persistence import save_interpretation
from app.services.narrative.assembler import assemble_narrative
from app.services.reflection_engine.client import ReflectionEngineClient
from app.services.scripture.selection import select_scripture_reflections
from app.services.scriptural_reflection.persistence import (
    get_current_scriptural_reflection,
    save_scriptural_reflection,
)


class ReadingNotReadyForInterpretationError(ValueError):
    """Raised by interpret_reading() when `reading.is_spread_complete` is
    False -- checked BEFORE engine.interpret() is invoked at all
    (Documentation/READING_INTEGRATION_DESIGN.md Section 3). Stronger than
    engine.interpret()'s own precondition (which only rejects a Reading
    with zero CardDraws); that check remains in place as defense-in-depth,
    not as the primary guard.
    """


def interpret_reading(session: Session, reading: Reading) -> Interpretation:
    """Runs the full Reading -> Interpretation Engine -> persistence
    sequence for `reading`
    (Documentation/READING_INTEGRATION_DESIGN.md Sections 2-5).

    Triggerable regardless of `reading.status`'s current value (DRAFTING,
    SPREAD_COMPLETE, INTERPRETED, or SAVED are all accepted) -- the only
    precondition is evidence-based: every required SpreadPosition on
    `reading.spread` must have a drawn card. Raises
    ReadingNotReadyForInterpretationError if not, before any engine or
    persistence call is made -- no Interpretation row is created and
    `reading.status` is left untouched.

    A new Interpretation row is always created on success, never reusing
    or overwriting a prior one (Section 6) -- calling this function again
    later against the same Reading is the entire reinterpretation
    mechanism; no special-case logic exists here for it. No duplicate-run
    detection or skipping is performed (Section 11, Resolved Q3 --
    deliberately deferred, not implemented).

    Does not commit or roll back -- see module docstring.
    """
    if not reading.is_spread_complete:
        raise ReadingNotReadyForInterpretationError(
            f"reading {reading.id} is not spread-complete: not every required "
            "position on its spread has a drawn card"
        )

    model: InterpretiveModel = interpret(reading, session)
    return save_interpretation(session, reading, model)


def get_current_interpretation(session: Session, reading: Reading) -> Interpretation | None:
    """The Interpretation row with the highest `sequence` for `reading`, or
    None if `reading` has never been interpreted
    (Documentation/READING_INTEGRATION_DESIGN.md Section 7, Resolved Q2).

    Exposed as its own reusable function (Step 11,
    INTERPRETATION_API_DESIGN.md Section 2.1) so callers such as the API
    layer never write this query themselves; `get_narrative_for_reading()`
    below is itself built on this function rather than duplicating it.
    """
    return session.execute(
        select(Interpretation)
        .where(Interpretation.reading_id == reading.id)
        .order_by(Interpretation.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_interpretations(session: Session, reading: Reading) -> list[Interpretation]:
    """Every Interpretation row for `reading`, newest-first (descending
    `sequence` -- the current interpretation is always index 0).

    Deliberately the opposite order of `Reading.interpretations`' own
    relationship ordering (ascending, chosen for the ORM's own convenience
    -- Documentation/READING_INTEGRATION_DESIGN.md Section 7): a history
    *list* is a different consumer with a different natural expectation
    (Step 11, INTERPRETATION_API_DESIGN.md Section 12).
    """
    return list(
        session.execute(
            select(Interpretation)
            .where(Interpretation.reading_id == reading.id)
            .order_by(Interpretation.sequence.desc())
        ).scalars()
    )


def get_narrative_for_reading(session: Session, reading: Reading) -> NarrativeModel | None:
    """Assembles the narrative for `reading`'s current interpretation --
    the Interpretation row with the highest `sequence` for this
    `reading_id` (Documentation/READING_INTEGRATION_DESIGN.md Section 7,
    Resolved Q2) -- or None if `reading` has never been interpreted.

    Performs the only database read anywhere in the narrative path: fetches
    the current Interpretation row via `get_current_interpretation()` and
    reconstructs its InterpretiveModel via `InterpretiveModel.model_validate(...)`
    (an already-proven-lossless round-trip --
    test_save_interpretation_round_trips_the_model_through_json), then
    hands that already-materialized object to the pure, database-free
    `assemble_narrative()` (NARRATIVE_LAYER_DESIGN.md Section 2/4).

    NarrativeModel is never persisted or cached here (Section 9, Resolved
    Q4) -- every call recomputes it from the persisted Interpretation. If
    narrative assembly itself raises, nothing about the already-persisted
    Interpretation row is touched or affected -- this function performs no
    write of any kind (Section 10/12).
    """
    latest = get_current_interpretation(session, reading)

    if latest is None:
        return None

    model = InterpretiveModel.model_validate(latest.interpretive_model)
    return assemble_narrative(model)


def get_scripture_for_reading(session: Session, reading: Reading) -> ScripturalPerspective | None:
    """Selects (or retrieves an already-persisted) Scriptural Reflection
    for `reading`'s current interpretation -- the Interpretation row with
    the highest `sequence` for this `reading_id` -- or None if `reading`
    has never been interpreted. Mirrors get_narrative_for_reading() above
    exactly, one layer over: same "reconstruct the persisted
    InterpretiveModel, hand it to a pure-with-respect-to-tarot-content
    downstream function" shape.

    Callers decide whether to call this at all -- that decision (never a
    stored flag, never a request parameter this function reads) is what
    makes Scripture "optional" at this foundation stage
    (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15.2's three-state user
    preference is future work; today, simply not calling this function is
    "Scripture Off").

    A ScripturalReflection snapshot, once created, is never recomputed --
    if `reading`'s current interpretation already has one (see
    get_current_scriptural_reflection_for_reading below), it is returned
    as-is, without touching select_scripture_reflections() or the
    ScriptureReference table at all, so a saved/reopened reading's
    Scriptural Reflection cannot silently change if the approved
    reference dataset is edited later. Only the *first* call for a given
    interpretation actually selects; and only when that selection finds
    at least one approved reference is a snapshot persisted --
    Documentation's own audit finding that an empty result must never be
    frozen (it would permanently hide a later addition to the approved
    dataset from a reading that has already been viewed).
    """
    latest = get_current_interpretation(session, reading)

    if latest is None:
        return None

    existing = get_current_scriptural_reflection(session, latest)
    if existing is not None:
        return ScripturalPerspective.model_validate(existing.scriptural_perspective)

    model = InterpretiveModel.model_validate(latest.interpretive_model)
    perspective = select_scripture_reflections(session, model)
    if perspective.reflections:
        save_scriptural_reflection(session, latest, perspective)
    return perspective


def get_current_ai_narrative(session: Session, interpretation: Interpretation) -> AINarrative | None:
    """The AINarrative row with the highest `sequence` for `interpretation`,
    or None if this specific interpretation has never had an AI narrative
    generated against it -- mirrors get_current_interpretation() above,
    one layer over. Scoped to `interpretation_id`, not `reading_id` (see
    AINarrative's own docstring for why): a Reading with a newer
    Interpretation than the one an AI narrative was generated against
    correctly reports "no current AI narrative" rather than surfacing a
    stale one.
    """
    return session.execute(
        select(AINarrative)
        .where(AINarrative.interpretation_id == interpretation.id)
        .order_by(AINarrative.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_current_ai_narrative_for_reading(session: Session, reading: Reading) -> AINarrative | None:
    """The current AI narrative for `reading`'s current interpretation, or
    None if `reading` has never been interpreted, or has been interpreted
    but has no AI narrative generated against its current interpretation
    yet. Both cases are indistinguishable to a caller by design -- see
    app/api/ai_narrative.py, which maps either to 404.
    """
    latest = get_current_interpretation(session, reading)
    if latest is None:
        return None
    return get_current_ai_narrative(session, latest)


def get_current_scriptural_reflection_for_reading(
    session: Session, reading: Reading
) -> ScripturalPerspective | None:
    """The already-persisted Scriptural Reflection for `reading`'s current
    interpretation, or None if `reading` has never been interpreted, or
    has been interpreted but has no ScripturalReflection snapshot
    persisted against its current interpretation yet. Both cases are
    indistinguishable to a caller by design -- mirrors
    get_current_ai_narrative_for_reading() exactly, one layer over
    (app/api/scripture.py maps either to 404).

    Never selects, computes, or persists anything -- a free, read-only
    check, safe to call on every page load (mirrors GET
    /ai-narrative/current's own contract). Never touches
    select_scripture_reflections() or the ScriptureReference table.
    """
    latest = get_current_interpretation(session, reading)
    if latest is None:
        return None
    existing = get_current_scriptural_reflection(session, latest)
    if existing is None:
        return None
    return ScripturalPerspective.model_validate(existing.scriptural_perspective)


def generate_ai_narrative_for_reading(
    session: Session,
    reading: Reading,
    client: ReflectionEngineClient,
    *,
    include_scripture: bool,
    provider: str,
    model: str,
) -> AINarrative | None:
    """Runs one AI Narrative Layer generation for `reading`'s current
    interpretation and persists the result, or None if `reading` has never
    been interpreted (checked before any Reflection Engine call is made,
    mirroring interpret_reading()'s own precondition-before-work shape).

    `include_scripture` is this call's own, never-stored opt-in -- mirrors
    get_scripture_for_reading()'s own "callers decide whether to call this
    at all" contract; there is no persisted per-User/per-Reading
    preference (SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md Section 4).
    When True, the *already-computed, already-approved* ScripturalPerspective
    is looked up via select_scripture_reflections() (never a second, AI-driven
    Scripture lookup) and handed to the AI Narrative Layer alongside the
    InterpretiveModel; the AI is never given the ability to introduce a
    Scripture reference this layer did not already select (see
    generation.py's own validation).

    If generation.generate_ai_narrative() raises (a ReflectionEngineError
    or a validation failure), that exception propagates unchanged -- this
    function has performed no database write by that point, so the
    Reading's Interpretation history is entirely unaffected by a failed AI
    call (Product Spec's own "a failed AI request does not corrupt or
    invalidate the deterministic reading" requirement). Persistence
    (save_ai_narrative) only ever runs after generation has already
    succeeded.
    """
    latest = get_current_interpretation(session, reading)
    if latest is None:
        return None

    model_obj = InterpretiveModel.model_validate(latest.interpretive_model)
    scripture: ScripturalPerspective | None = None
    if include_scripture:
        scripture = select_scripture_reflections(session, model_obj)

    context = build_deterministic_reading_context(model_obj, scripture)
    response: AINarrativeResponse = generate_ai_narrative(client, context, provider=provider, model=model)
    return save_ai_narrative(session, latest, response)
