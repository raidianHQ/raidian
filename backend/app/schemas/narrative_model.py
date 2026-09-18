"""The structured, deterministic output of Narrative Assembly (Step 7).

Concretizes Documentation/NARRATIVE_LAYER_DESIGN.md Section 5 into a typed
schema. Pure data shape, no computation -- mirrors
schemas/interpretive_model.py's own "just data shape, no computation"
discipline.

Named `NarrativeModel` per the Step 7 implementation instruction. The
design document itself sketches this shape as "NarrativeDocument" --
same fields, same contract; this is the implementation's chosen name,
not a functional deviation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.interpretive_model import Citation


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class NarrativeStatement(_Model):
    """One deterministically-assembled sentence/phrase.

    `citations` are copied verbatim from the InterpretiveModel entry this
    statement renders -- never recomputed or newly constructed (design doc
    Section 8). Unlike InterpretiveModel.Explained.citations, this may
    legitimately be empty: connective/metadata statements (e.g. the
    central_question quote, the Overall Reflection recap) assert nothing
    beyond what their own section already establishes elsewhere and so
    carry no citation of their own.
    """

    text: str
    citations: tuple[Citation, ...] = ()


class NarrativeSection(_Model):
    """One section of the narrative, in the fixed order
    Documentation/NARRATIVE_LAYER_DESIGN.md Section 6 specifies.

    `present=False` means this section's source InterpretiveModel field
    was null and the section was deliberately omitted (design doc Section
    10, Rule N10a) -- `statements` is empty in that case. Every section
    always appears in NarrativeModel.sections regardless of `present`, so
    a consumer can rely on a fixed section count/order rather than a
    variable-length list.
    """

    id: str
    title: str
    source_field: str | None
    present: bool
    statements: tuple[NarrativeStatement, ...] = ()


class NarrativeModel(_Model):
    """One complete, deterministic narrative assembled from exactly one
    InterpretiveModel. See Documentation/NARRATIVE_LAYER_DESIGN.md Section
    5 for the field-by-field contract this mirrors exactly.
    """

    schema_version: str
    narrative_template_version: str
    source_schema_version: str
    source_engine_version: str
    source_reference_data_version: str
    generated_at: datetime

    sections: tuple[NarrativeSection, ...]
