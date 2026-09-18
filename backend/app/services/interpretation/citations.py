"""Shared Citation-construction helpers, so every stage builds citations
the same way instead of re-deriving the same field mapping repeatedly.
"""

from __future__ import annotations

from app.schemas.interpretive_model import Citation, RuleTier, SourceType
from app.services.interpretation.context import DrawContext


def citation_for_draw(draw: DrawContext, *, contributing_theme: str | None = None) -> Citation:
    return Citation(
        source_type="card_draw",
        card_draw_id=draw.card_draw_id,
        card_name=draw.card_name,
        position_name=draw.position_name,
        position_semantic_role=draw.semantic_role.value,
        contributing_theme=contributing_theme,
    )


def citation_for_rule(
    *, rule_id: str, rule_tier: RuleTier, source_type: SourceType = "compound_rule"
) -> Citation:
    return Citation(source_type=source_type, rule_id=rule_id, rule_tier=rule_tier)
