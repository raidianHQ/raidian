"""The AI Narrative Layer's own input/output contract
(RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 12, ADR-0005's Reflection Engine).

Mirrors schemas/narrative_model.py and schemas/scripture_model.py's own
"just data shape, no computation" discipline -- the actual generation logic
lives in app/services/ai_narrative/.

    DeterministicReadingContext   -- everything the AI is allowed to know
            |                         (an InterpretiveModel plus an
            v                         optional ScripturalPerspective --
    (Reflection Engine call)          never raw Card Draws, never a
            |                         second, independent Scripture
            v                         lookup)
    AINarrativeResponse           -- the validated, structured result
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.scripture_model import ScripturalPerspective


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DeterministicReadingContext(_Model):
    """The AI Narrative Layer's entire factual basis for one request --
    deliberately just a thin wrapper around two already-deterministic
    objects, not a duplicate reshaping of their fields (that would risk
    the two copies drifting, exactly the failure mode
    SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md's own separation table
    warns against).

    `interpretation` already carries everything Product Spec Section 12
    asks the AI input to include: central_question, spread_name/
    spread_description, card_interpretations, relationships, theme_strength,
    primary_tension, contradictions, trajectory, deterministic_synthesis.

    `scripture` is populated only when the caller explicitly opted in for
    this request (mirrors GET /readings/{id}/scripture's own per-call,
    never-stored opt-in -- see SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md
    Section 4). None here means "do not mention Scripture at all" -- the
    AI Narrative Layer must not fabricate its own Scripture lookup; the
    only Scripture data it can ever see is whatever the deterministic
    Scripture Layer already selected.
    """

    interpretation: InterpretiveModel
    scripture: ScripturalPerspective | None = None


class AINarrativeResponse(_Model):
    """One validated AI Narrative generation result
    (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 12's suggested section
    structure, reshaped into the task's suggested structured-field output).

    Every field here is natural-language prose the Reflection Engine wrote
    -- unlike InterpretiveModel's Explained[T]/Citation machinery, nothing
    here carries its own citation, because an AI-generated sentence's
    precise provenance cannot be mechanically verified the way a
    deterministic rule's can. The *content* it is allowed to draw from is
    constrained instead, at the input boundary (DeterministicReadingContext
    above) and by generation.py's post-response validation -- see that
    module for the specific checks (e.g. no scriptural_reflection when
    `scripture` was not supplied).

    `key_themes` and `card_relationships` are natural-language statements
    (one entry per theme/relationship worth naming), not a single fused
    paragraph -- "structured fields rather than one uncontrolled text
    blob" (the task's own requirement), without inventing citation objects
    the AI cannot actually back.
    """

    schema_version: str
    source_schema_version: str
    generated_at: datetime
    provider: str
    model: str

    opening_summary: str
    overall_narrative: str
    key_themes: tuple[str, ...] = Field(min_length=1)
    card_relationships: tuple[str, ...] = ()
    reflective_synthesis: str
    reflection_questions: tuple[str, ...] = Field(min_length=1)
    scriptural_reflection: str | None = None


class AINarrativeSummary(_Model):
    """Full AI narrative content plus its row-level provenance -- mirrors
    schemas/interpretation_api.py::InterpretationSummary exactly, one
    layer over. Returned by POST /readings/{id}/ai-narrative and
    GET /readings/{id}/ai-narrative/current.
    """

    id: UUID
    interpretation_id: UUID
    sequence: int
    created_at: datetime
    ai_narrative: AINarrativeResponse
