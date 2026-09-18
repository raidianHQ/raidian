"""Stage 10-11: uncertainty identification + interpretive evidence strength.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stages 10-11; Section 10.7 and
10.11 for what each output field means. `uncertainty` is REQUIRED (never
omitted, even when evidence is strong -- Section 10.7) and
`evidence_strength` is explicitly NOT a prediction-confidence score
(Section 10.11), only a measure of how much structural/thematic signal
this foundation's stages found.
"""

from __future__ import annotations

from app.schemas.interpretive_model import EvidenceStrength, Explained, Trajectory
from app.services.interpretation.compounds import CompoundMatch
from app.services.interpretation.structure import StructuralFindings

# Fixed, ordered checklist -- each condition is checked in this literal
# sequence, never via dict/set iteration, so the resulting tuple's order
# is always the same for the same inputs.


def identify_uncertainty(
    structure: StructuralFindings,
    trajectory: Explained[Trajectory] | None,
    compound_matches: tuple[CompoundMatch, ...],
) -> tuple[str, ...]:
    statements: list[str] = []

    if trajectory is None:
        statements.append(
            "This spread's positions do not establish a clear temporal trajectory "
            "(no Recent Past, Situation, and Near Future roles together)."
        )
    if structure.advice is None:
        statements.append(
            "This spread does not include an Advice position, so no guidance is derived "
            "from spread structure alone."
        )
    elif structure.advice_clarifier is None:
        statements.append(
            "This spread does not include an Advice Clarifier position, so the advice "
            "above is not further qualified."
        )
    if structure.blocker is None:
        statements.append(
            "This spread does not identify a specific Influence/Blocker position."
        )
    if not compound_matches:
        statements.append(
            "None of the currently defined named thematic patterns were found in this "
            "spread's drawn cards."
        )

    return tuple(statements)


def score_evidence_strength(
    structure: StructuralFindings,
    trajectory: Explained[Trajectory] | None,
    compound_matches: tuple[CompoundMatch, ...],
) -> EvidenceStrength:
    """A simple, provisional point count for this foundation phase --
    explicitly not a probability or confidence score (Section 10.11). One
    point each for: a derived trajectory, a situation/blocker adjacency, an
    advice/clarifier pairing, and each fired compound-theme rule.

    Thresholds (0 / 1 / 2-3 / 4+) are a deliberately simple starting
    heuristic, not a validated model -- refining them is future work that
    does not require touching this function's signature or callers.
    """
    signal_count = 0
    if trajectory is not None:
        signal_count += 1
    if structure.has_situation_blocker_adjacency:
        signal_count += 1
    if structure.has_advice_clarifier_pairing:
        signal_count += 1
    signal_count += len(compound_matches)

    if signal_count == 0:
        return "unresolved"
    if signal_count == 1:
        return "weak"
    if signal_count <= 3:
        return "moderate"
    return "strong"
