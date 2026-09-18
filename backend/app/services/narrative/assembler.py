"""The deterministic Narrative Assembly pipeline orchestrator (Step 7).

Pure function: assemble_narrative() takes exactly one InterpretiveModel
and returns exactly one NarrativeModel. No database session, no
reference-data lookup, no reading/card/correspondence access, no
network or other I/O -- see
Documentation/NARRATIVE_LAYER_DESIGN.md Section 2 ("Single input") and
Section 4 for why this is a hard architectural requirement, not a style
preference: it is what keeps this layer downstream-only and prevents it
from silently reintroducing raw evidence access the engine's own
citations were designed to make unnecessary.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.interpretive_model import InterpretiveModel
from app.schemas.narrative_model import NarrativeModel
from app.services.narrative.sections import (
    assemble_advice,
    assemble_central_theme,
    assemble_clarification,
    assemble_overall_reflection,
    assemble_the_tension,
    assemble_what_may_be_unclear,
    assemble_what_stands_in_the_way,
    assemble_what_the_spread_shows,
    assemble_where_things_appear_to_be_moving,
    assemble_your_reading,
)

SCHEMA_VERSION = "1.0"

# Bumped whenever section wording or assembly logic changes -- deliberately
# independent of the source InterpretiveModel's own engine_version/
# schema_version (design doc Section 9: a template wording change is not
# an engine change, and vice versa).
NARRATIVE_TEMPLATE_VERSION = "0.1.0-foundation"


def assemble_narrative(model: InterpretiveModel) -> NarrativeModel:
    """Runs every N1-N10 section rule against `model`, in the fixed
    section order Documentation/NARRATIVE_LAYER_DESIGN.md Section 6
    specifies, and assembles the result into one NarrativeModel.

    All 10 sections are always present in the returned tuple (in this
    fixed order), even when a section's own `present` flag is False --
    so a consumer can rely on a fixed section count and order rather than
    a variable-length list (design doc Section 5's `present: bool` note).
    """
    sections = (
        assemble_your_reading(model),
        assemble_central_theme(model),
        assemble_the_tension(model),
        assemble_what_stands_in_the_way(model),
        assemble_what_the_spread_shows(model),
        assemble_where_things_appear_to_be_moving(model),
        assemble_what_may_be_unclear(model),
        assemble_advice(model),
        assemble_clarification(model),
        assemble_overall_reflection(model),
    )

    return NarrativeModel(
        schema_version=SCHEMA_VERSION,
        narrative_template_version=NARRATIVE_TEMPLATE_VERSION,
        source_schema_version=model.schema_version,
        source_engine_version=model.engine_version,
        source_reference_data_version=model.reference_data_version,
        generated_at=datetime.now(timezone.utc),
        sections=sections,
    )
