"""Stage 9: contradiction detection.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stage 9: "competing signals that
should be surfaced, not silently resolved."

Deliberately conservative for this foundation phase: it always returns an
empty tuple. Defining what counts as a genuine "contradiction" between two
cards' themes requires a rule about which theme pairs meaningfully oppose
each other -- that is exactly the kind of interpretive judgment the engine
must not invent (compare compounds.py's refusal to guess unmapped theme
names). The two compound rules seeded so far (compounds.py) model a
*tension held together* ("Clarity vs. Uncertainty"), not a contradiction
in the product spec's sense of competing signals that can't be reconciled
-- conflating the two would misrepresent what either concept means.

This stage exists as a real, tested, callable function (so the pipeline's
structure is complete and the InterpretiveModel.contradictions field is
always populated, even if empty) rather than being silently omitted.
Meaningful contradiction detection is future work, gated on a deliberately
authored rule set, not something to approximate here.
"""

from __future__ import annotations

from app.schemas.interpretive_model import Contradiction
from app.services.interpretation.compounds import CompoundMatch
from app.services.interpretation.context import ReadingContext


def detect_contradictions(
    reading_context: ReadingContext, compound_matches: tuple[CompoundMatch, ...]
) -> tuple[Contradiction, ...]:
    del reading_context, compound_matches  # unused by design in this foundation phase
    return ()
