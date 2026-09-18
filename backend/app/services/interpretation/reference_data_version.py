"""Computes `reference_data_version`: a deterministic content hash of every
piece of reference data the Interpretation Engine is allowed to read
(Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 3.1), so two
interpretation runs can be verified to have used identical reference data
rather than merely assumed to have (design doc Section 9, Q2).

Deliberately a *content* hash, not a hash of row identity: primary keys are
random UUIDs regenerated on every fresh seed, so sorting or hashing by `id`
would make the version change even when nothing about the content did.
Every row is sorted by a stable, content-derived key (name) instead, and
`id`/`created_at`/`updated_at` are excluded from the hashed payload
entirely -- they describe storage, not content.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, CardCorrespondence, Deck, Spread, SpreadPosition
from app.seed.loader import load_theme_vocabulary


def _card_payload(card: Card) -> dict:
    return {
        "name": card.name,
        "arcana": card.arcana.value,
        "suit": card.suit.value if card.suit else None,
        "rank": card.rank,
        "image_ref": card.image_ref,
        "base_meaning_upright": card.base_meaning_upright,
        "base_meaning_reversed": card.base_meaning_reversed,
        "keywords": list(card.keywords),
        "primary_themes": list(card.primary_themes),
        "secondary_themes": list(card.secondary_themes),
    }


def _correspondence_payload(corr: CardCorrespondence) -> dict:
    return {
        "card_name": corr.card.name,
        "source_reference": corr.source_reference,
        "tradition_name": corr.tradition_name,
        "element": corr.element,
        "zodiac_signs": list(corr.zodiac_signs),
        "zodiac_symbols": list(corr.zodiac_symbols),
        "astrological_influence": corr.astrological_influence,
        "elemental_gender": corr.elemental_gender,
        "direction": corr.direction,
        "color": corr.color,
        "animal": corr.animal,
        "stone": corr.stone,
        "astrology_note": corr.astrology_note,
    }


def _spread_payload(spread: Spread) -> dict:
    positions: list[SpreadPosition] = sorted(spread.positions, key=lambda p: p.position_order)
    return {
        "name": spread.name,
        "description": spread.description,
        "allow_duplicate_cards": spread.allow_duplicate_cards,
        "positions": [
            {
                "name": p.name,
                "description": p.description,
                "position_order": p.position_order,
                "semantic_role": p.semantic_role.value,
                "required": p.required,
            }
            for p in positions
        ],
    }


def _deck_payload(deck: Deck) -> dict:
    return {
        "name": deck.name,
        "description": deck.description,
        "is_default": deck.is_default,
    }


def compute_reference_data_version(session: Session) -> str:
    """Returns a hex SHA-256 digest of the canonical serialization of all
    currently-readable reference data. Same content (regardless of row
    insertion order or which UUIDs got assigned) always yields the same
    digest; any content change yields a different one.
    """
    decks = session.scalars(select(Deck)).all()
    cards = session.scalars(select(Card)).all()
    correspondences = session.scalars(select(CardCorrespondence)).all()
    spreads = session.scalars(select(Spread)).all()
    theme_vocabulary = load_theme_vocabulary()

    payload = {
        "decks": sorted((_deck_payload(d) for d in decks), key=lambda d: d["name"]),
        "cards": sorted((_card_payload(c) for c in cards), key=lambda c: c["name"]),
        "correspondences": sorted(
            (_correspondence_payload(c) for c in correspondences), key=lambda c: c["card_name"]
        ),
        "spreads": sorted((_spread_payload(s) for s in spreads), key=lambda s: s["name"]),
        "theme_vocabulary": sorted(theme_vocabulary),
    }

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
