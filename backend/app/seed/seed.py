"""Loads the validated reference-data content (app.seed.loader) into the
database.

This is deliberately kept separate from application/API logic -- it is a
data-loading concern, not a request-handling one. It is safe to run
repeatedly: every entity is upserted by its natural key (Deck.name,
Card.(deck_id, name), Spread.name, SpreadPosition.(spread_id,
position_order)), so re-running it against a database that already has this
data updates existing rows in place rather than erroring or duplicating
them. That also means correcting a card's wording later is just an edit to
its YAML file followed by re-running the seed -- no new migration needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, CardCorrespondence, Deck, ScriptureReference, Spread, SpreadPosition
from app.models.enums import Arcana, SemanticRole, Suit
from app.seed.loader import (
    RWS_DECK_DIR,
    SCRIPTURE_REFERENCES_PATH,
    SPREADS_DIR,
    load_all_spread_definitions,
    load_card_definitions,
    load_correspondence_definitions,
    load_deck_definition,
    load_scripture_reference_definitions,
    validate_card_definitions,
    validate_correspondence_definitions,
    validate_scripture_reference_definitions,
    validate_spread_definition,
)


@dataclass
class SeedSummary:
    deck: Deck
    spreads: list[Spread]
    correspondences: list[CardCorrespondence]
    scripture_references: list[ScriptureReference]


def seed_deck(session: Session, deck_dir: Path = RWS_DECK_DIR) -> Deck:
    deck_def = load_deck_definition(deck_dir)
    card_defs = load_card_definitions(deck_dir)
    validate_card_definitions(card_defs)

    deck = session.scalars(select(Deck).where(Deck.name == deck_def["name"])).one_or_none()
    if deck is None:
        deck = Deck(name=deck_def["name"])
        session.add(deck)
    deck.description = deck_def.get("description")
    deck.is_default = bool(deck_def.get("is_default", False))
    session.flush()

    existing_cards_by_name = {card.name: card for card in deck.cards}
    for card_def in card_defs:
        card = existing_cards_by_name.get(card_def["name"])
        if card is None:
            card = Card(deck=deck, name=card_def["name"])
            session.add(card)

        card.arcana = Arcana(card_def["arcana"])
        card.suit = Suit(card_def["suit"]) if card_def.get("suit") else None
        card.rank = card_def["rank"]
        card.image_ref = card_def["image_ref"]
        card.base_meaning_upright = card_def["base_meaning_upright"].strip()
        card.base_meaning_reversed = card_def["base_meaning_reversed"].strip()
        card.keywords = list(card_def["keywords"])
        card.primary_themes = list(card_def["primary_themes"])
        card.secondary_themes = list(card_def["secondary_themes"])

    session.flush()
    return deck


def seed_card_correspondences(
    session: Session, deck: Deck, deck_dir: Path = RWS_DECK_DIR
) -> list[CardCorrespondence]:
    """Seeds the astrological/elemental correspondence layer for `deck`'s
    cards -- a distinct, separately-sourced layer from the card meanings in
    seed_deck() above. See RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md.

    Requires `deck` to already have its cards seeded (deck.cards populated)
    in this session -- call after seed_deck(), not standalone.
    """
    card_defs = load_card_definitions(deck_dir)
    correspondence_defs = load_correspondence_definitions(deck_dir)
    validate_correspondence_definitions(card_defs, correspondence_defs)

    cards_by_name = {card.name: card for card in deck.cards}
    correspondences: list[CardCorrespondence] = []

    for entry in correspondence_defs:
        card = cards_by_name[entry["name"]]
        correspondence = card.correspondence
        if correspondence is None:
            correspondence = CardCorrespondence(card=card)
            session.add(correspondence)

        correspondence.source_reference = entry["source_reference"]
        correspondence.tradition_name = entry.get("tradition_name")
        correspondence.element = entry["element"]
        correspondence.zodiac_signs = list(entry["zodiac_signs"])
        correspondence.zodiac_symbols = list(entry["zodiac_symbols"])
        correspondence.astrological_influence = entry["astrological_influence"]
        correspondence.elemental_gender = entry.get("elemental_gender")
        correspondence.direction = entry["direction"]
        correspondence.color = entry["color"]
        correspondence.animal = entry.get("animal")
        correspondence.stone = entry.get("stone")
        correspondence.astrology_note = entry.get("astrology_note")
        correspondences.append(correspondence)

    session.flush()
    return correspondences


def seed_scripture_references(
    session: Session, path: Path = SCRIPTURE_REFERENCES_PATH
) -> list[ScriptureReference]:
    """Seeds the approved Scripture reference dataset for the optional
    Scriptural Reflection layer (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section
    15) -- content entirely separate from the tarot deck/spreads seeded
    above; keyed by theme, never by Card, so it has no dependency on
    seed_deck() having run first.

    Upserted by natural key (theme, book, chapter, verse_start,
    translation), mirroring seed_deck()/seed_spread()'s own
    re-runnable-by-natural-key discipline.
    """
    entries = load_scripture_reference_definitions(path)
    validate_scripture_reference_definitions(entries)

    existing_by_key = {
        (row.theme, row.book, row.chapter, row.verse_start, row.translation): row
        for row in session.scalars(select(ScriptureReference)).all()
    }
    references: list[ScriptureReference] = []
    for entry in entries:
        key = (entry["theme"], entry["book"], entry["chapter"], entry["verse_start"], entry["translation"])
        reference = existing_by_key.get(key)
        if reference is None:
            reference = ScriptureReference(
                theme=entry["theme"],
                book=entry["book"],
                chapter=entry["chapter"],
                verse_start=entry["verse_start"],
                translation=entry["translation"],
            )
            session.add(reference)

        reference.verse_end = entry.get("verse_end")
        reference.reference_display = entry["reference_display"]
        reference.context_note = entry["context_note"].strip()
        reference.reflection_connection = entry["reflection_connection"].strip()
        references.append(reference)

    session.flush()
    return references


def seed_spread(session: Session, spread_def: dict) -> Spread:
    validate_spread_definition(spread_def)

    spread = session.scalars(select(Spread).where(Spread.name == spread_def["name"])).one_or_none()
    if spread is None:
        spread = Spread(name=spread_def["name"])
        session.add(spread)
    spread.description = spread_def.get("description")
    spread.allow_duplicate_cards = bool(spread_def.get("allow_duplicate_cards", False))
    session.flush()

    existing_positions_by_order = {position.position_order: position for position in spread.positions}
    for position_def in spread_def["positions"]:
        position = existing_positions_by_order.get(position_def["position_order"])
        if position is None:
            position = SpreadPosition(spread=spread, position_order=position_def["position_order"])
            session.add(position)

        position.name = position_def["name"]
        position.description = position_def.get("description")
        position.semantic_role = SemanticRole(position_def["semantic_role"])
        position.required = bool(position_def["required"])

    session.flush()
    return spread


def seed_all_spreads(session: Session, spreads_dir: Path = SPREADS_DIR) -> list[Spread]:
    return [seed_spread(session, spread_def) for spread_def in load_all_spread_definitions(spreads_dir)]


def seed_reference_data(session: Session) -> SeedSummary:
    """Seeds the MVP deck and its cards, the initial MVP spreads, and the
    approved Scripture reference dataset.

    Does not commit -- the caller controls the transaction boundary (tests
    typically flush and roll back; the CLI entrypoint below commits).
    """
    deck = seed_deck(session)
    correspondences = seed_card_correspondences(session, deck)
    spreads = seed_all_spreads(session)
    scripture_references = seed_scripture_references(session)
    return SeedSummary(
        deck=deck, spreads=spreads, correspondences=correspondences,
        scripture_references=scripture_references,
    )


def main() -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        summary = seed_reference_data(session)
        session.commit()

        print(f"Seeded deck '{summary.deck.name}' ({len(summary.deck.cards)} cards)")
        print(f"Seeded {len(summary.correspondences)} card correspondence records")
        for spread in summary.spreads:
            print(f"Seeded spread '{spread.name}' ({len(spread.positions)} positions)")
        print(f"Seeded {len(summary.scripture_references)} scripture reference records")


if __name__ == "__main__":
    main()
