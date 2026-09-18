"""Stage 7: structural relationships tied to Spread/SpreadPosition
structure itself.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stage 7: "e.g. advice/clarifier
pairing, situation/blocker adjacency". Presence-based only for this
foundation phase -- it identifies *which* draws occupy these structural
roles (there is at most one of each per Spread, since SemanticRole is a
single value per SpreadPosition); it does not attempt to score how
strongly they relate, which would require an invented weighting scheme.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import SemanticRole
from app.services.interpretation.context import DrawContext, ReadingContext


@dataclass(frozen=True)
class StructuralFindings:
    situation: DrawContext | None
    blocker: DrawContext | None
    advice: DrawContext | None
    advice_clarifier: DrawContext | None
    significator: DrawContext | None

    @property
    def has_situation_blocker_adjacency(self) -> bool:
        return self.situation is not None and self.blocker is not None

    @property
    def has_advice_clarifier_pairing(self) -> bool:
        return self.advice is not None and self.advice_clarifier is not None


def _single_draw_with_role(reading_context: ReadingContext, role: SemanticRole) -> DrawContext | None:
    matches = reading_context.draws_with_role(role)
    return matches[0] if matches else None


def evaluate_structure(reading_context: ReadingContext) -> StructuralFindings:
    return StructuralFindings(
        situation=_single_draw_with_role(reading_context, SemanticRole.SITUATION),
        blocker=_single_draw_with_role(reading_context, SemanticRole.INFLUENCE_BLOCKER),
        advice=_single_draw_with_role(reading_context, SemanticRole.ADVICE),
        advice_clarifier=_single_draw_with_role(reading_context, SemanticRole.ADVICE_CLARIFIER),
        significator=_single_draw_with_role(reading_context, SemanticRole.SIGNIFICATOR),
    )
