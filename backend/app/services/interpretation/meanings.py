"""Stage 1-2: card meaning resolution + theme strength scoring.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stages 1-2.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.schemas.interpretive_model import Citation
from app.services.interpretation.citations import citation_for_draw
from app.services.interpretation.context import ReadingContext


def resolve_meanings(reading_context: ReadingContext) -> dict[UUID, str]:
    """Stage 1: the already-selected (upright/reversed) meaning text per
    draw. Resolution itself happened in context.build_reading_context();
    this just exposes it keyed by card_draw_id for stages/citations that
    want to quote it.
    """
    return {draw.card_draw_id: draw.meaning_text for draw in reading_context.draws}


@dataclass(frozen=True)
class ThemeScore:
    """How many of the drawn cards support a given theme tag, and which
    draws they were.
    """

    theme: str
    count: int
    citations: tuple[Citation, ...]


def score_theme_strength(reading_context: ReadingContext) -> tuple[ThemeScore, ...]:
    """Stage 2: frequency of each theme tag across all drawn cards'
    primary_themes + secondary_themes (context.DrawContext.all_themes).

    Deterministic ordering: by count descending, then by theme name
    ascending as a fixed, content-derived tiebreak -- never by dict/set
    iteration order (INTERPRETATION_ENGINE_DESIGN.md Section 5/10).
    """
    counts: dict[str, int] = {}
    citations_by_theme: dict[str, list[Citation]] = {}

    for draw in reading_context.draws:
        for theme in draw.all_themes:
            counts[theme] = counts.get(theme, 0) + 1
            citations_by_theme.setdefault(theme, []).append(
                citation_for_draw(draw, contributing_theme=theme)
            )

    scores = [
        ThemeScore(theme=theme, count=count, citations=tuple(citations_by_theme[theme]))
        for theme, count in counts.items()
    ]
    scores.sort(key=lambda s: (-s.count, s.theme))
    return tuple(scores)
