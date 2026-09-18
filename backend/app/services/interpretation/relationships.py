"""Stage 5: card-to-card relationships.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stage 5: "pairwise/groupwise
relationships between drawn cards (e.g. same-suit clustering, Major Arcana
density, numerological sequences)".

Only the two relationship types with an unambiguous, mechanical
definition are implemented here: same-suit clustering (cards literally
sharing a Suit) and Major Arcana density (a plain count). "Numerological
sequences" is not implemented -- deciding what counts as a meaningful
sequence would require inventing a rule not specified anywhere, which the
engine's design constraints rule out.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Suit
from app.services.interpretation.context import DrawContext, ReadingContext


@dataclass(frozen=True)
class SuitCluster:
    suit: Suit
    draws: tuple[DrawContext, ...]


@dataclass(frozen=True)
class CardRelationships:
    same_suit_clusters: tuple[SuitCluster, ...]
    major_arcana_draws: tuple[DrawContext, ...]

    @property
    def major_arcana_count(self) -> int:
        return len(self.major_arcana_draws)


def evaluate_relationships(reading_context: ReadingContext) -> CardRelationships:
    by_suit: dict[Suit, list[DrawContext]] = {}
    major_arcana: list[DrawContext] = []

    for draw in reading_context.draws:
        if draw.suit is not None:
            by_suit.setdefault(draw.suit, []).append(draw)
        if draw.arcana.value == "major":
            major_arcana.append(draw)

    # Only suits with 2+ drawn cards count as a "cluster". Sorted by suit
    # name for determinism (Suit is a str enum, so this is a stable,
    # content-derived order, not iteration-order-dependent).
    clusters = tuple(
        SuitCluster(suit=suit, draws=tuple(draws))
        for suit, draws in sorted(by_suit.items(), key=lambda item: item[0].value)
        if len(draws) >= 2
    )

    return CardRelationships(
        same_suit_clusters=clusters,
        major_arcana_draws=tuple(major_arcana),
    )
